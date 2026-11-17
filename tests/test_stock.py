"""Tests du stock : réception, FEFO, sécurité et intégrité."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase  # noqa: F401

from .base import BaseTestCase
from django.utils import timezone

from achats.services import receptionner_commande, valider_commande, creer_commande
from stock.allocation import allouer_lots_fefo
from stock.exceptions import StockInsuffisantError
from stock.models import LotStock, MouvementStock
from stock.services import corriger_quantite, verifier_integrite
from ventes.models import Vente
from ventes.services import creer_vente

from .factories import Fabrique


class ReceptionStockTests(BaseTestCase):
    def test_reception_de_20_unites_cree_le_stock_et_un_mouvement(self):
        medicament = Fabrique.medicament()
        utilisateur = Fabrique.utilisateur('stock-a', 'gestionnaire_stock')

        Fabrique.commande_receptionnee(medicament, quantite=20, utilisateur=utilisateur)

        self.assertEqual(medicament.stock_disponible, 20)
        lot = LotStock.objects.get(medicament=medicament)
        self.assertEqual(lot.quantite, 20)
        self.assertEqual(lot.quantite_initiale, 20)
        mouvement = MouvementStock.objects.get(lot=lot)
        self.assertEqual(mouvement.type, MouvementStock.Type.ENTREE)
        self.assertEqual(mouvement.quantite, 20)
        self.assertEqual(verifier_integrite(), [])

    def test_sur_reception_est_refusee(self):
        medicament = Fabrique.medicament()
        utilisateur = Fabrique.utilisateur('stock-b', 'gestionnaire_stock')
        commande = creer_commande(
            Fabrique.fournisseur(), utilisateur,
            [{'medicament': medicament, 'quantite': 5,
              'prix_unitaire': medicament.prix_achat}],
        )
        valider_commande(commande, utilisateur)
        ligne = commande.lignes.get()

        with self.assertRaises(ValidationError):
            receptionner_commande(
                commande,
                [{'ligne_achat': ligne, 'medicament': medicament,
                  'numero_lot': 'LOT-X',
                  'date_peremption': timezone.localdate() + timedelta(days=100),
                  'quantite': 6, 'prix_unitaire': medicament.prix_achat}],
                utilisateur,
            )
        self.assertEqual(medicament.stock_disponible, 0)

    def test_reception_lot_perime_est_refusee(self):
        medicament = Fabrique.medicament()
        utilisateur = Fabrique.utilisateur('stock-c', 'gestionnaire_stock')
        commande = creer_commande(
            Fabrique.fournisseur(), utilisateur,
            [{'medicament': medicament, 'quantite': 10,
              'prix_unitaire': medicament.prix_achat}],
        )
        valider_commande(commande, utilisateur)
        ligne = commande.lignes.get()

        with self.assertRaises(ValidationError):
            receptionner_commande(
                commande,
                [{'ligne_achat': ligne, 'medicament': medicament,
                  'numero_lot': 'LOT-P',
                  'date_peremption': timezone.localdate() - timedelta(days=1),
                  'quantite': 10, 'prix_unitaire': medicament.prix_achat}],
                utilisateur,
            )
        self.assertFalse(LotStock.objects.filter(medicament=medicament).exists())


class FEFOTests(BaseTestCase):
    def setUp(self):
        self.medicament = Fabrique.medicament()
        self.utilisateur = Fabrique.utilisateur('vendeur-fefo', 'caissier')

    def test_lot_le_plus_proche_de_la_peremption_est_utilise_en_priorite(self):
        lot_lointain = Fabrique.lot(self.medicament, 'LOT-LOIN', 10, jours=400)
        lot_proche = Fabrique.lot(self.medicament, 'LOT-PROCHE', 10, jours=30)

        allocations = allouer_lots_fefo(self.medicament, 12)

        self.assertEqual(allocations[0][0].pk, lot_proche.pk)
        self.assertEqual(allocations[0][1], 10)
        self.assertEqual(allocations[1][0].pk, lot_lointain.pk)
        self.assertEqual(allocations[1][1], 2)

    def test_lots_perimes_et_bloques_sont_exclus(self):
        Fabrique.lot(self.medicament, 'LOT-PERIME', 10, jours=-1)
        Fabrique.lot(self.medicament, 'LOT-BLOQUE', 10, jours=50, bloque=True)
        valide = Fabrique.lot(self.medicament, 'LOT-VALIDE', 5, jours=100)

        allocations = allouer_lots_fefo(self.medicament, 5)

        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0][0].pk, valide.pk)

    def test_stock_insuffisant_leve_une_erreur_sans_decrementer(self):
        Fabrique.lot(self.medicament, 'LOT-FAIBLE', 2, jours=100)

        with self.assertRaises(StockInsuffisantError):
            allouer_lots_fefo(self.medicament, 3)

        self.assertEqual(self.medicament.stock_disponible, 2)
        self.assertFalse(Vente.objects.exists())

    def test_vente_de_3_unites_decremente_le_stock_et_trace_la_sortie(self):
        lot = Fabrique.lot(self.medicament, 'LOT-VENTE', 20, jours=100)

        vente = creer_vente(
            [{'medicament': self.medicament, 'quantite': 3}], self.utilisateur
        )

        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 17)
        self.assertEqual(self.medicament.stock_disponible, 17)
        self.assertEqual(vente.total, Decimal('1500'))
        sortie = MouvementStock.objects.get(
            lot=lot, type=MouvementStock.Type.SORTIE
        )
        self.assertEqual(sortie.quantite, -3)
        self.assertEqual(sortie.reference, vente.numero)
        self.assertEqual(verifier_integrite(), [])

    def test_vente_impossible_sans_stock_ne_cree_rien(self):
        with self.assertRaises(StockInsuffisantError):
            creer_vente(
                [{'medicament': self.medicament, 'quantite': 1}], self.utilisateur
            )
        self.assertFalse(Vente.objects.exists())
        self.assertFalse(MouvementStock.objects.exists())


class CorrectionStockTests(BaseTestCase):
    def test_correction_inventaire_est_tracee_et_non_negative(self):
        medicament = Fabrique.medicament()
        lot = Fabrique.lot(medicament, 'LOT-INV', 10, jours=100)
        utilisateur = Fabrique.utilisateur('inv-user', 'gestionnaire_stock')

        corriger_quantite(lot, 14, motif='Inventaire physique', utilisateur=utilisateur)

        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 14)
        mouvement = MouvementStock.objects.get(type=MouvementStock.Type.CORRECTION)
        self.assertEqual(mouvement.quantite, 4)
        self.assertEqual(verifier_integrite(), [])

        with self.assertRaises(ValidationError):
            corriger_quantite(lot, -1, motif='Erreur', utilisateur=utilisateur)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite, 14)

    def test_controle_integrite_detecte_une_quantite_incoherente(self):
        medicament = Fabrique.medicament()
        lot = Fabrique.lot(medicament, 'LOT-INC', 10, jours=100)

        self.assertEqual(verifier_integrite(), [])
        # Une écriture directe, sans mouvement, simule une incohérence.
        LotStock.objects.filter(pk=lot.pk).update(quantite=13)

        incoherences = verifier_integrite(medicament)
        self.assertEqual(len(incoherences), 1)
        self.assertEqual(incoherences[0][1], 13)
        self.assertEqual(incoherences[0][2], 10)
