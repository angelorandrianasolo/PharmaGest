"""Tests de la gestion des fournisseurs : accès, CRUD, recherche et traçabilité."""

from django.urls import reverse

from achats.services import creer_commande
from core.models import JournalAudit

from .base import BaseTestCase
from .factories import Fabrique
from fournisseurs.models import Fournisseur


class FournisseurAccessTests(BaseTestCase):
    def test_acces_a_la_liste_selon_le_role(self):
        liste = reverse('fournisseurs:liste')
        reponse = self.client.get(liste)
        self.assertRedirects(
            reponse, f"{reverse('utilisateurs:login')}?next={liste}",
            fetch_redirect_response=False,
        )

        self.client.force_login(Fabrique.utilisateur('fourn-caissier', 'caissier'))
        self.assertEqual(self.client.get(liste).status_code, 403)

        self.client.force_login(Fabrique.utilisateur('fourn-gestion', 'gestionnaire_stock'))
        self.assertEqual(self.client.get(liste).status_code, 200)

    def test_actions_visibles_selon_les_permissions(self):
        Fabrique.fournisseur('Laboratoire Test')
        gestion = Fabrique.utilisateur('fourn-actions-gestion', 'gestionnaire_stock')
        self.client.force_login(gestion)
        contenu = self.client.get(reverse('fournisseurs:liste')).content.decode()
        self.assertIn('Nouveau fournisseur', contenu)
        self.assertIn('Modifier', contenu)

        responsable = Fabrique.utilisateur('fourn-actions-resp', 'responsable_gestion')
        self.client.force_login(responsable)
        contenu = self.client.get(reverse('fournisseurs:liste')).content.decode()
        self.assertIn('Fournisseurs', contenu)
        self.assertNotIn('Nouveau fournisseur', contenu)

    def test_liste_ordre_alphabetique_et_proprietes_du_modele(self):
        Fabrique.fournisseur('Zeta Pharma')
        Fabrique.fournisseur('Alpha Santé')
        gestion = Fabrique.utilisateur('fourn-ordre', 'gestionnaire_stock')
        self.client.force_login(gestion)

        reponse = self.client.get(reverse('fournisseurs:liste'))
        self.assertEqual(
            [f.nom for f in reponse.context['fournisseurs']],
            ['Alpha Santé', 'Zeta Pharma'],
        )
        self.assertEqual(str(reponse.context['fournisseurs'][0]), 'Alpha Santé')
        self.assertEqual(reponse.context['fournisseurs'][0].nombre_commandes, 0)
        self.assertEqual(reponse.context['fournisseurs'][0].montant_commandes, 0)

    def test_recherche_par_nom_et_par_telephone(self):
        Fabrique.fournisseur('Pharma Distribution').telephone  # création simple
        Fournisseur.objects.filter(nom='Pharma Distribution').update(telephone='032 12 34 56')
        Fabrique.fournisseur('Autre Fournisseur')
        self.client.force_login(Fabrique.utilisateur('fourn-recherche', 'gestionnaire_stock'))

        reponse = self.client.get(reverse('fournisseurs:liste'), {'q': 'distribution'})
        self.assertEqual([f.nom for f in reponse.context['fournisseurs']],
                         ['Pharma Distribution'])
        reponse = self.client.get(reverse('fournisseurs:liste'), {'q': '12 34'})
        self.assertEqual([f.nom for f in reponse.context['fournisseurs']],
                         ['Pharma Distribution'])

    def test_pagination_de_la_liste(self):
        for i in range(21):
            Fabrique.fournisseur(f'Fournisseur {i:02d}')
        self.client.force_login(Fabrique.utilisateur('fourn-page', 'gestionnaire_stock'))

        reponse = self.client.get(reverse('fournisseurs:liste'))
        self.assertTrue(reponse.context['is_paginated'])
        self.assertEqual(len(reponse.context['fournisseurs']), 20)
        self.assertContains(reponse, 'Page 1 / 2')
        self.assertContains(reponse, 'Suivant')

        reponse = self.client.get(reverse('fournisseurs:liste'), {'page': 2})
        self.assertEqual(len(reponse.context['fournisseurs']), 1)


class FournisseurCrudTests(BaseTestCase):
    def setUp(self):
        self.gestion = Fabrique.utilisateur('fourn-crud', 'gestionnaire_stock')
        self.client.force_login(self.gestion)

    def test_creation_avec_tous_les_champs(self):
        reponse = self.client.post(reverse('fournisseurs:creer'), {
            'nom': 'Nouveau Laboratoire',
            'adresse': '12 rue de la Pharmacie',
            'telephone': '032 00 00 00',
            'email': 'contact@labo.mg',
            'identifiant_fiscal': 'IF-1234',
            'contact_principal': 'Mme Razafy',
            'actif': 'on',
        })
        self.assertRedirects(reponse, reverse('fournisseurs:liste'))
        fournisseur = Fournisseur.objects.get(nom='Nouveau Laboratoire')
        self.assertTrue(fournisseur.actif)
        self.assertEqual(fournisseur.email, 'contact@labo.mg')
        self.assertEqual(fournisseur.identifiant_fiscal, 'IF-1234')

    def test_creation_invalide_sans_nom(self):
        reponse = self.client.post(reverse('fournisseurs:creer'), {'nom': ''})
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('nom', reponse.context['form'].errors)
        self.assertFalse(Fournisseur.objects.exists())

    def test_modification_et_refus_pour_le_responsable(self):
        fournisseur = Fabrique.fournisseur('Ancien Nom')
        url = reverse('fournisseurs:modifier', args=[fournisseur.pk])
        reponse = self.client.post(url, {
            'nom': 'Nom Modifié', 'telephone': '032 99 99 99', 'actif': 'on',
        })
        self.assertRedirects(reponse, reverse('fournisseurs:liste'))
        fournisseur.refresh_from_db()
        self.assertEqual(fournisseur.nom, 'Nom Modifié')

        self.client.force_login(Fabrique.utilisateur('fourn-refus', 'responsable_gestion'))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_detail_avec_historique_des_commandes(self):
        fournisseur = Fabrique.fournisseur('Fournisseur Commandes')
        medicament = Fabrique.medicament()
        commande = creer_commande(
            fournisseur, self.gestion,
            [{'medicament': medicament, 'quantite': 5,
              'prix_unitaire': medicament.prix_achat}],
        )
        reponse = self.client.get(reverse('fournisseurs:detail', args=[fournisseur.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Historique des commandes')
        self.assertContains(reponse, commande.numero)
        self.assertContains(reponse, reverse('achats:commande_detail', args=[commande.pk]))
        self.assertEqual(len(reponse.context['commandes']), 1)
        self.assertEqual(self.client.get(
            reverse('fournisseurs:detail', args=[99999])
        ).status_code, 404)

    def test_basculer_actif_est_trace_sans_supprimer(self):
        fournisseur = Fabrique.fournisseur('Fournisseur Bascule')
        url = reverse('fournisseurs:basculer_actif', args=[fournisseur.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

        self.client.post(url)
        fournisseur.refresh_from_db()
        self.assertFalse(fournisseur.actif)
        self.assertTrue(Fournisseur.objects.filter(pk=fournisseur.pk).exists())
        self.assertTrue(JournalAudit.objects.filter(
            action='Fournisseur désactivé', modele='fournisseur',
            objet_id=str(fournisseur.pk),
        ).exists())

        self.client.post(url)
        fournisseur.refresh_from_db()
        self.assertTrue(fournisseur.actif)
        self.assertTrue(JournalAudit.objects.filter(
            action='Fournisseur activé', modele='fournisseur',
        ).exists())
