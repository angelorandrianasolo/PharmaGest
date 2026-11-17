"""Tests des documents PDF et du tableau de bord."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.http import HttpResponse
from django.test import TestCase  # noqa: F401
from django.utils import timezone

from achats.services import creer_commande
from ventes.models import LigneVente, Paiement, Vente
from ventes.services import creer_vente
from rapports.views import RapportAchatsPdfView, RapportVentesPdfView

from .base import BaseTestCase
from django.urls import reverse

from .factories import Fabrique


class PdfTests(BaseTestCase):
    def setUp(self):
        self.admin = Fabrique.utilisateur('admin-pdf', 'administrateur', is_superuser=True,
                                          is_staff=True)
        self.client.force_login(self.admin)

    def test_recu_et_facture_sont_des_pdf_valides(self):
        medicament = Fabrique.medicament()
        Fabrique.lot(medicament, 'LOT-PDF', 10, jours=100)
        vente = creer_vente(
            [{'medicament': medicament, 'quantite': 2}], self.admin
        )

        for name in ('recu', 'facture'):
            response = self.client.get(reverse(f'rapports:{name}', args=[vente.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertTrue(response.content.startswith(b'%PDF'))

    def test_rapports_stock_peremptions_et_periodes(self):
        medicament = Fabrique.medicament()
        Fabrique.lot(medicament, 'LOT-RAP', 5, jours=100)

        for name in ('rapport_stock', 'rapport_peremptions', 'rapport_ventes',
                     'rapport_achats'):
            response = self.client.get(reverse(f'rapports:{name}'))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b'%PDF'))


class TableauDeBordTests(BaseTestCase):
    def test_dashboard_affiche_les_indicateurs(self):
        gestion = Fabrique.utilisateur('gestion-dash', 'responsable_gestion')
        gestion.synchroniser_groupes()
        medicament = Fabrique.medicament()
        Fabrique.lot(medicament, 'LOT-DASH', 3, jours=100)
        self.client.force_login(gestion)

        response = self.client.get(reverse('rapports:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tableau de bord')
        self.assertContains(response, medicament.nom)


class TableauDeBordAvanceTests(BaseTestCase):
    def test_acces_au_tableau_de_bord_selon_le_role(self):
        tableau = reverse('rapports:dashboard')
        self.assertRedirects(
            self.client.get(tableau),
            f"{reverse('utilisateurs:login')}?next={tableau}",
            fetch_redirect_response=False,
        )
        for role in ('pharmacien', 'gestionnaire_stock', 'responsable_gestion'):
            with self.subTest(role=role):
                self.client.force_login(Fabrique.utilisateur(f'rapport-{role}', role))
                reponse = self.client.get(tableau)
                self.assertEqual(reponse.status_code, 200)
                self.assertContains(reponse, reverse('rapports:rapport_stock'))
                self.assertContains(reponse, 'Tableau de bord')
        for role in ('caissier', 'inscrit'):
            with self.subTest(role=role):
                self.client.force_login(Fabrique.utilisateur(f'rapport-{role}', role))
                self.assertEqual(self.client.get(tableau).status_code, 403)

    def test_indicateurs_du_jour_excluent_les_ventes_annulees(self):
        admin = Fabrique.utilisateur('rapport-kpi', 'administrateur')
        self.client.force_login(admin)
        medicament = Fabrique.medicament()
        Vente.objects.create(numero='VTE-KPI-1', utilisateur=admin,
                             total=Decimal('1000'), statut=Vente.STATUT_CONFIRMEE)
        Vente.objects.create(numero='VTE-KPI-2', utilisateur=admin,
                             total=Decimal('500'), statut=Vente.STATUT_ANNULEE)
        Paiement.objects.create(
            vente=Vente.objects.get(numero='VTE-KPI-1'), montant=Decimal('700'),
            statut=Paiement.STATUT_CONFIRME, confirme_le=timezone.now(),
        )
        Paiement.objects.create(
            vente=Vente.objects.get(numero='VTE-KPI-2'), montant=Decimal('300'),
            statut=Paiement.STATUT_CONFIRME,
            confirme_le=timezone.now() - timedelta(days=3),
        )
        LigneVente.objects.create(
            vente=Vente.objects.get(numero='VTE-KPI-1'), medicament=medicament,
            quantite=2, prix_unitaire=Decimal('500'),
        )

        contexte = self.client.get(reverse('rapports:dashboard')).context
        self.assertEqual(contexte['medicaments_actifs'], 1)
        self.assertEqual(contexte['ventes_du_jour'], 1)
        self.assertEqual(contexte['ca_du_jour'], 1000)
        self.assertEqual(contexte['encaissements'], 700)
        self.assertEqual(contexte['marge'], 500)

    def test_alertes_de_stock_et_de_peremption(self):
        admin = Fabrique.utilisateur('rapport-alertes', 'administrateur')
        self.client.force_login(admin)
        sans_lot = Fabrique.medicament('Produit Sans Lot', seuil=5)
        proche = Fabrique.medicament('Produit Proche Peremption')
        Fabrique.lot(proche, 'LOT-PROCHE', 5, jours=10)
        perime = Fabrique.medicament('Produit Perime')
        Fabrique.lot(perime, 'LOT-PERIME', 3, jours=-1)

        reponse = self.client.get(reverse('rapports:dashboard'))
        noms_faibles = [m.nom for m in reponse.context['stocks_faibles']]
        self.assertIn(sans_lot.nom, noms_faibles)
        self.assertEqual(
            [lot.numero_lot for lot in reponse.context['peremptions_proches']],
            ['LOT-PROCHE'],
        )
        self.assertEqual(
            [lot.numero_lot for lot in reponse.context['lots_perimes']], ['LOT-PERIME']
        )
        self.assertContains(reponse, 'Stocks faibles')
        self.assertContains(reponse, 'Péremptions à 30 jours')

    def test_graphiques_sur_sept_jours_et_produits_les_plus_vendus(self):
        admin = Fabrique.utilisateur('rapport-graph', 'administrateur')
        self.client.force_login(admin)
        medicament = Fabrique.medicament('Produit Populaire')
        for i, quantite in enumerate((3, 5), start=1):
            vente = Vente.objects.create(
                numero=f'VTE-TOP-{i}', utilisateur=admin,
                total=Decimal('100'), statut=Vente.STATUT_CONFIRMEE,
            )
            LigneVente.objects.create(
                vente=vente, medicament=medicament, quantite=quantite,
                prix_unitaire=medicament.prix_vente,
            )
        annulee = Vente.objects.create(
            numero='VTE-TOP-ANN', utilisateur=admin, total=Decimal('1000'),
            statut=Vente.STATUT_ANNULEE,
        )
        LigneVente.objects.create(
            vente=annulee, medicament=medicament, quantite=100,
            prix_unitaire=medicament.prix_vente,
        )

        contexte = self.client.get(reverse('rapports:dashboard')).context
        self.assertEqual(len(contexte['ventes_par_jour']), 7)
        self.assertEqual(len(contexte['achats_par_jour']), 7)
        self.assertEqual(contexte['ventes_par_jour'][-1]['valeur'], 200.0)
        self.assertEqual(contexte['top_produits'][0]['medicament__nom'], 'Produit Populaire')
        self.assertEqual(contexte['top_produits'][0]['total_vendu'], 8)

    def test_etats_vides_du_tableau_de_bord(self):
        self.client.force_login(Fabrique.utilisateur('rapport-vide', 'administrateur'))
        reponse = self.client.get(reverse('rapports:dashboard'))
        self.assertContains(reponse, 'Aucune alerte.')
        self.assertContains(reponse, 'Aucune.')
        self.assertContains(reponse, 'Aucun.')
        self.assertContains(reponse, 'Aucune vente.')


class DocumentsPdfAvancesTests(BaseTestCase):
    def setUp(self):
        self.admin = Fabrique.utilisateur('rapport-pdf-admin', 'administrateur')
        self.client.force_login(self.admin)
        medicament = Fabrique.medicament()
        Fabrique.lot(medicament, 'LOT-PDF-AV', 6, jours=100)
        self.vente = creer_vente([{'medicament': medicament, 'quantite': 2}], self.admin)
        fournisseur = Fabrique.fournisseur()
        self.commande = creer_commande(
            fournisseur, self.admin,
            [{'medicament': medicament, 'quantite': 10,
              'prix_unitaire': medicament.prix_achat}],
        )
        self.reception = Fabrique.commande_receptionnee(
            Fabrique.medicament('Produit Recu'), quantite=4, utilisateur=self.admin
        ).receptions.first()

    def test_contrat_http_des_documents_pdf(self):
        cas = (
            ('recu', [self.vente.pk], 'recu-'),
            ('facture', [self.vente.pk], 'facture-'),
            ('bon_commande', [self.commande.pk], 'bon-commande-'),
            ('bon_reception', [self.reception.pk], 'bon-reception-'),
            ('rapport_stock', [], 'rapport-stock'),
            ('rapport_peremptions', [], 'rapport-peremptions'),
            ('rapport_ventes', [], 'rapport-ventes'),
            ('rapport_achats', [], 'rapport-achats'),
        )
        for route, args, nom in cas:
            with self.subTest(route=route):
                reponse = self.client.get(reverse(f'rapports:{route}', args=args))
                self.assertEqual(reponse.status_code, 200)
                self.assertEqual(reponse['Content-Type'], 'application/pdf')
                self.assertTrue(reponse.content.startswith(b'%PDF'))
                self.assertIn(f'filename="{nom}', reponse['Content-Disposition'])

    def test_permissions_des_documents_sont_distinguees(self):
        caissier = Fabrique.utilisateur('rapport-pdf-caissier', 'caissier')
        self.client.force_login(caissier)
        for route in ('recu', 'facture'):
            with self.subTest(route=route):
                reponse = self.client.get(reverse(f'rapports:{route}', args=[self.vente.pk]))
                self.assertEqual(reponse.status_code, 200)
        for route, args in (('bon_commande', [self.commande.pk]),
                            ('bon_reception', [self.reception.pk]),
                            ('rapport_stock', [])):
            with self.subTest(route=route):
                self.assertEqual(
                    self.client.get(reverse(f'rapports:{route}', args=args)).status_code, 403
                )

        responsable = Fabrique.utilisateur('rapport-pdf-resp', 'responsable_gestion')
        self.client.force_login(responsable)
        for route, args in (('bon_commande', [self.commande.pk]),
                            ('rapport_stock', [])):
            with self.subTest(route=route):
                reponse = self.client.get(reverse(f'rapports:{route}', args=args))
                self.assertEqual(reponse.status_code, 200)

    def test_documents_introuvables_et_filtre_de_periode(self):
        for route in ('recu', 'bon_commande', 'bon_reception'):
            with self.subTest(route=route):
                self.assertEqual(
                    self.client.get(reverse(f'rapports:{route}', args=[99999])).status_code,
                    404,
                )

        fin = timezone.localdate()
        debut = fin - timedelta(days=15)
        reponse = self.client.get(reverse('rapports:rapport_ventes'),
                                  {'debut': debut.isoformat(), 'fin': fin.isoformat()})
        self.assertEqual(reponse.status_code, 200)
        with patch.object(RapportVentesPdfView, 'generateur',
                          return_value=HttpResponse(b'%PDF')) as generateur:
            self.client.get(reverse('rapports:rapport_ventes'),
                            {'debut': debut.isoformat(), 'fin': fin.isoformat()})
            generateur.assert_called_once_with(debut, fin)

        with patch.object(RapportVentesPdfView, 'generateur',
                          return_value=HttpResponse(b'%PDF')) as generateur:
            self.client.get(reverse('rapports:rapport_ventes'), {'debut': 'pas-une-date'})
            appel = generateur.call_args[0]
            self.assertEqual(appel[1], fin)
            self.assertEqual(appel[0], fin - timedelta(days=30))

        with patch.object(RapportAchatsPdfView, 'generateur',
                          return_value=HttpResponse(b'%PDF')) as generateur:
            self.client.get(reverse('rapports:rapport_achats'))
            appel = generateur.call_args[0]
            self.assertEqual(appel[0], fin - timedelta(days=30))
