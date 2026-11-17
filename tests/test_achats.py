"""Tests des achats : commandes, réceptions, stock et traçabilité."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from achats.models import CommandeAchat, ReceptionAchat
from achats.services import (
    annuler_commande,
    creer_commande,
    receptionner_commande,
    valider_commande,
)
from core.models import JournalAudit
from stock.models import LotStock, MouvementStock
from stock.services import verifier_integrite
from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique


class CommandeAchatTests(BaseTestCase):
    def setUp(self):
        self.gestion = Fabrique.utilisateur('achats-gestion', 'gestionnaire_stock')
        self.admin = Fabrique.utilisateur('achats-admin', 'administrateur')
        self.fournisseur = Fabrique.fournisseur('Fournisseur Achats')
        self.medicament = Fabrique.medicament()
        self.client.force_login(self.gestion)

    def _commande(self, quantite=10):
        return creer_commande(
            self.fournisseur, self.gestion,
            [{'medicament': self.medicament, 'quantite': quantite,
              'prix_unitaire': self.medicament.prix_achat}],
        )

    def test_acces_et_pagination_des_commandes(self):
        liste = reverse('achats:liste')
        self.client.logout()
        self.assertRedirects(
            self.client.get(liste),
            f"{reverse('utilisateurs:login')}?next={liste}",
            fetch_redirect_response=False,
        )
        self.client.force_login(Fabrique.utilisateur('achats-caissier', 'caissier'))
        self.assertEqual(self.client.get(liste).status_code, 403)

        self.client.force_login(self.gestion)
        commande = self._commande()
        reponse = self.client.get(liste)
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, commande.numero)
        self.assertContains(reponse, 'Nouvelle commande')

        for i in range(21):
            creer_commande(
                self.fournisseur, self.gestion,
                [{'medicament': self.medicament, 'quantite': 1,
                  'prix_unitaire': Decimal('250')}],
            )
        reponse = self.client.get(liste)
        self.assertTrue(reponse.context['is_paginated'])
        self.assertEqual(len(reponse.context['commandes']), 20)
        self.assertContains(reponse, 'Page 1 / 2')

    def test_creation_dune_commande_via_le_formulaire(self):
        reponse = self.client.post(reverse('achats:commande_creer'), {
            'fournisseur': self.fournisseur.pk,
            'date_commande': timezone.localdate().isoformat(),
            'note': 'Commande de test',
            'lignes-TOTAL_FORMS': '2',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-medicament': self.medicament.pk,
            'lignes-0-quantite': '10',
            'lignes-0-prix_unitaire': '250',
            'lignes-1-medicament': '',
        })
        commande = CommandeAchat.objects.get(note='Commande de test')
        self.assertRedirects(reponse, reverse('achats:commande_detail', args=[commande.pk]))
        self.assertEqual(commande.statut, CommandeAchat.STATUT_BROUILLON)
        self.assertTrue(commande.numero.startswith('CMD-'))
        self.assertEqual(commande.cree_par, self.gestion)
        self.assertEqual(commande.total, Decimal('2500'))
        self.assertTrue(JournalAudit.objects.filter(
            action='Commande créée', objet_id=str(commande.pk)
        ).exists())
        self.assertIn('Commande créée en brouillon.',
                      [str(m) for m in reponse.wsgi_request._messages])

    def test_creation_avec_lignes_invalides_est_refusee(self):
        reponse = self.client.post(reverse('achats:commande_creer'), {
            'fournisseur': self.fournisseur.pk,
            'date_commande': timezone.localdate().isoformat(),
            'lignes-TOTAL_FORMS': '1',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-medicament': self.medicament.pk,
            'lignes-0-quantite': '0',
            'lignes-0-prix_unitaire': '250',
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context['formset'].errors)
        self.assertFalse(CommandeAchat.objects.exists())

        with self.assertRaisesMessage(ValidationError, 'Une commande doit contenir au moins une ligne.'):
            creer_commande(self.fournisseur, self.gestion, [])

    def test_detail_affiche_les_actions_selon_le_statut(self):
        commande = self._commande()
        reponse = self.client.get(reverse('achats:commande_detail', args=[commande.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, commande.numero)
        contenu = reponse.content.decode()
        self.assertIn('Valider', contenu)
        self.assertIn('Réceptionner', contenu)
        # Le gestionnaire n'a pas la permission annuler_commande.
        self.assertNotIn('>Annuler</button>', contenu)
        self.assertIn(reverse('rapports:bon_commande', args=[commande.pk]), contenu)
        self.assertEqual(len(reponse.context['receptions']), 0)
        self.assertEqual(self.client.get(
            reverse('achats:commande_detail', args=[99999])
        ).status_code, 404)

    def test_validation_est_tracée_et_non_repetable(self):
        commande = self._commande()
        url = reverse('achats:commande_valider', args=[commande.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

        self.client.post(url)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeAchat.STATUT_COMMANDEE)
        self.assertTrue(JournalAudit.objects.filter(
            action='Commande validée', objet_id=str(commande.pk)
        ).exists())

        self.client.post(url)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeAchat.STATUT_COMMANDEE)

        with self.assertRaisesMessage(
            ValidationError, 'Seule une commande en brouillon peut être validée.'
        ):
            valider_commande(commande, self.gestion)

    def test_annulation_reservee_a_ladministrateur(self):
        commande = self._commande()
        url = reverse('achats:commande_annuler', args=[commande.pk])
        # Le gestionnaire n'a pas la permission : refus avant même le contrôle de méthode.
        self.assertEqual(self.client.post(url).status_code, 403)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeAchat.STATUT_ANNULEE)
        self.assertTrue(JournalAudit.objects.filter(
            action='Commande annulée', objet_id=str(commande.pk)
        ).exists())

        commande_receptionnee = Fabrique.commande_receptionnee(
            Fabrique.medicament('Produit Annulable'), utilisateur=self.admin
        )
        with self.assertRaisesMessage(
            ValidationError, 'Une commande déjà réceptionnée ne peut pas être annulée.'
        ):
            annuler_commande(commande_receptionnee, self.admin)

    def test_formulaire_de_reception_limite_les_lignes(self):
        commande = self._commande()
        autre_commande = self._commande()
        reponse = self.client.get(reverse('achats:reception_creer', args=[commande.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.context['formset'].forms), 1)
        lignes = reponse.context['formset'].forms[0].fields['ligne_achat'].queryset
        self.assertEqual([l.pk for l in lignes], [l.pk for l in commande.lignes.all()])
        self.assertNotIn(autre_commande.lignes.first().pk, [l.pk for l in lignes])
        self.assertEqual(self.client.get(
            reverse('achats:reception_creer', args=[99999])
        ).status_code, 404)

    def _donnees_reception(self, commande, **surcharges):
        ligne = commande.lignes.first()
        donnees = {
            'note': 'Réception de test',
            'lignes-TOTAL_FORMS': '1',
            'lignes-INITIAL_FORMS': '0',
            'lignes-MIN_NUM_FORMS': '0',
            'lignes-MAX_NUM_FORMS': '1000',
            'lignes-0-ligne_achat': ligne.pk,
            'lignes-0-medicament': ligne.medicament_id,
            'lignes-0-numero_lot': 'LOT-ACHAT',
            'lignes-0-date_peremption': (timezone.localdate() + timedelta(days=200)).isoformat(),
            'lignes-0-quantite': '4',
            'lignes-0-prix_unitaire': '250',
        }
        donnees.update(surcharges)
        return donnees

    def test_reception_partielle_puis_totale_met_a_jour_le_stock(self):
        commande = self._commande(quantite=10)
        url = reverse('achats:reception_creer', args=[commande.pk])
        reponse = self.client.post(url, self._donnees_reception(commande))
        self.assertRedirects(reponse, reverse('achats:commande_detail', args=[commande.pk]))
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeAchat.STATUT_PARTIELLE)
        self.assertEqual(commande.quantite_receptionnee, 4)
        self.assertEqual(ReceptionAchat.objects.count(), 1)
        self.assertEqual(LotStock.objects.get(numero_lot='LOT-ACHAT').quantite, 4)
        self.assertEqual(MouvementStock.objects.filter(type='entree').count(), 1)
        self.assertEqual(verifier_integrite(), [])

        self.client.post(url, self._donnees_reception(
            commande, **{'lignes-0-numero_lot': 'LOT-ACHAT-2', 'lignes-0-quantite': '6'}
        ))
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeAchat.STATUT_TOTALE)
        self.assertEqual(commande.quantite_receptionnee, 10)
        self.assertEqual(verifier_integrite(), [])

    def test_receptions_invalides_sont_atomiques(self):
        commande = self._commande(quantite=10)
        url = reverse('achats:reception_creer', args=[commande.pk])
        cas = (
            ({'lignes-0-date_peremption': (timezone.localdate() - timedelta(days=1)).isoformat()},
             'Un lot périmé ne peut pas être réceptionné.'),
            ({'lignes-0-quantite': '0'}, None),
            ({'lignes-0-quantite': '11'}, 'Réception supérieure à la quantité commandée'),
        )
        for surcharges, message in cas:
            with self.subTest(surcharges=surcharges):
                reponse = self.client.post(url, self._donnees_reception(commande, **surcharges))
                self.assertEqual(reponse.status_code, 200)
                self.assertFalse(ReceptionAchat.objects.exists())
                self.assertFalse(LotStock.objects.exists())
                self.assertFalse(MouvementStock.objects.exists())
                messages = [str(m) for m in reponse.wsgi_request._messages]
                if message:
                    self.assertTrue(any(message in m for m in messages), messages)
                self.assertContains(reponse, 'alert-danger')

    def test_documents_et_indicateurs_apres_reception(self):
        commande = self._commande(quantite=5)
        self.client.post(
            reverse('achats:reception_creer', args=[commande.pk]),
            self._donnees_reception(commande, **{'lignes-0-quantite': '5'}),
        )
        reception = ReceptionAchat.objects.get()

        for route, pk in (('bon_commande', commande.pk), ('bon_reception', reception.pk)):
            with self.subTest(route=route):
                reponse = self.client.get(reverse(f'rapports:{route}', args=[pk]))
                self.assertEqual(reponse.status_code, 200)
                self.assertEqual(reponse['Content-Type'], 'application/pdf')
                self.assertIn('.pdf', reponse['Content-Disposition'])

        dashboard = self.client.get(reverse('rapports:dashboard'))
        self.assertEqual(dashboard.context['ventes_par_jour'][-1]['jour'],
                         timezone.localdate().strftime('%a %d/%m'))
        self.assertEqual(dashboard.context['achats_par_jour'][-1]['valeur'], 5.0)

        accueil = self.client.get(reverse('home'))
        self.assertEqual(accueil.context['receptions_du_jour'], 1)
