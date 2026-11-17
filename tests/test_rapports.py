"""Tests des documents PDF et du tableau de bord."""

from django.test import TestCase  # noqa: F401

from .base import BaseTestCase
from django.urls import reverse

from ventes.services import creer_vente

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
