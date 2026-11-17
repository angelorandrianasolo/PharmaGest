"""Tests des ventes : atomicité, idempotence, paiements et retours."""

import threading
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase  # noqa: F401

from .base import BaseTestCase

from core.models import JournalAudit
from medicaments.models import Medicament
from stock.models import LotStock, MouvementStock
from ventes.models import LigneVente, Paiement, RetourVente, Vente
from ventes.services import (
    annuler_vente,
    confirmer_paiement,
    creer_retour,
    creer_vente,
)

from .factories import Fabrique


class VenteTests(BaseTestCase):
    def setUp(self):
        self.medicament = Fabrique.medicament()
        self.caissier = Fabrique.utilisateur('caissier-test', 'caissier')
        self.lot = Fabrique.lot(self.medicament, 'LOT-VTE', 10, jours=100)

    def test_vente_especes_est_confirmee_et_paiement_encaisse(self):
        vente = creer_vente(
            [{'medicament': self.medicament, 'quantite': 2}],
            self.caissier,
            mode_paiement=Vente.MODE_ESPECES,
        )
        self.assertEqual(vente.statut, Vente.STATUT_CONFIRMEE)
        paiement = vente.paiements.get()
        self.assertEqual(paiement.statut, Paiement.STATUT_CONFIRME)
        self.assertEqual(paiement.montant, Decimal('1000'))
        self.assertTrue(JournalAudit.objects.filter(action='Vente validée').exists())

    def test_vente_mobile_money_reste_en_attente_jusqu_a_confirmation(self):
        vente = creer_vente(
            [{'medicament': self.medicament, 'quantite': 1}],
            self.caissier,
            mode_paiement=Vente.MODE_MOBILE_MONEY,
        )
        self.assertEqual(vente.statut, Vente.STATUT_EN_ATTENTE)
        self.assertEqual(vente.paiements.get().statut, Paiement.STATUT_EN_ATTENTE)

        paiement = vente.paiements.get()
        confirmer_paiement(paiement, 'MM-REF-123', self.caissier)

        vente.refresh_from_db()
        paiement.refresh_from_db()
        self.assertEqual(vente.statut, Vente.STATUT_CONFIRMEE)
        self.assertEqual(paiement.statut, Paiement.STATUT_CONFIRME)
        self.assertEqual(paiement.reference, 'MM-REF-123')

    def test_idempotence_empeche_les_doubles_validations(self):
        cle = uuid.uuid4()
        lignes = [{'medicament': self.medicament, 'quantite': 2}]
        premiere = creer_vente(lignes, self.caissier, idempotency_key=cle)
        seconde = creer_vente(lignes, self.caissier, idempotency_key=cle)

        self.assertEqual(premiere.pk, seconde.pk)
        self.assertEqual(Vente.objects.count(), 1)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite, 8)
        self.assertEqual(MouvementStock.objects.filter(
            type=MouvementStock.Type.SORTIE
        ).count(), 1)

    def test_prix_et_lot_sont_figes_sur_la_ligne(self):
        vente = creer_vente(
            [{'medicament': self.medicament, 'quantite': 1}], self.caissier
        )
        ligne = vente.lignes.get()
        self.assertEqual(ligne.numero_lot, 'LOT-VTE')
        self.assertEqual(ligne.prix_unitaire, Decimal('500'))

        self.medicament.prix_vente = Decimal('999')
        self.medicament.save()
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_unitaire, Decimal('500'))

    def test_medicament_archive_ne_peut_pas_etre_vendu(self):
        self.medicament.statut = Medicament.STATUT_ARCHIVE
        self.medicament.save()
        with self.assertRaises(ValidationError):
            creer_vente(
                [{'medicament': self.medicament, 'quantite': 1}], self.caissier
            )


class RetourVenteTests(BaseTestCase):
    def setUp(self):
        self.medicament = Fabrique.medicament()
        self.caissier = Fabrique.utilisateur('caissier-retour', 'caissier')
        self.lot = Fabrique.lot(self.medicament, 'LOT-RETOUR', 10, jours=100)
        self.vente = creer_vente(
            [{'medicament': self.medicament, 'quantite': 3}], self.caissier
        )
        self.ligne = self.vente.lignes.get()

    def test_retour_compense_sans_supprimer_la_vente(self):
        retour = creer_retour(self.ligne, 1, 'Produit non conforme', self.caissier)

        self.assertTrue(retour.remis_en_stock)
        self.assertEqual(retour.montant_rembourse, Decimal('500'))
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite, 8)
        self.assertTrue(self.vente.statut == Vente.STATUT_CONFIRMEE)
        self.assertTrue(RetourVente.objects.filter(pk=retour.pk).exists())
        self.assertEqual(MouvementStock.objects.filter(
            type=MouvementStock.Type.RETOUR
        ).count(), 1)

    def test_retour_superieur_a_la_ligne_est_refuse(self):
        with self.assertRaises(ValidationError):
            creer_retour(self.ligne, 4, 'Erreur', self.caissier)
        self.assertFalse(RetourVente.objects.exists())

    def test_annulation_genere_des_retours_et_rembourse_le_paiement(self):
        annuler_vente(self.vente, 'Annulation client', self.caissier)

        self.vente.refresh_from_db()
        self.assertEqual(self.vente.statut, Vente.STATUT_ANNULEE)
        self.assertEqual(self.vente.paiements.get().statut, Paiement.STATUT_REMBOURSE)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite, 10)
        self.assertEqual(RetourVente.objects.count(), 1)

    def test_lot_perime_n_est_pas_reintegre_lors_d_un_retour(self):
        from datetime import timedelta

        from django.utils import timezone

        self.lot.date_peremption = timezone.localdate() - timedelta(days=1)
        self.lot.save()
        retour = creer_retour(self.ligne, 1, 'Retour tardif', self.caissier)
        self.assertFalse(retour.remis_en_stock)
        self.assertEqual(MouvementStock.objects.filter(
            type=MouvementStock.Type.RETOUR
        ).count(), 0)


class VenteConcurrenceTests(TransactionTestCase):
    """Deux validations simultanées avec la même clé ne doivent former qu'une vente."""

    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.medicament = Fabrique.medicament(nom='Paracétamol concurrence')
        self.caissier = Fabrique.utilisateur('caissier-concurrence', 'caissier')
        self.lot = Fabrique.lot(self.medicament, 'LOT-CONC', 10, jours=100)

    def test_deux_threads_avec_la_meme_cle_ne_creent_qu_une_vente(self):
        cle = uuid.uuid4()
        lignes = [{'medicament': self.medicament, 'quantite': 2}]
        barriere = threading.Barrier(2)
        ventes = []
        erreurs = []

        def valider():
            try:
                barriere.wait(timeout=10)
                ventes.append(creer_vente(lignes, self.caissier, idempotency_key=cle))
            except Exception as exc:  # pragma: no cover - diagnostic de test
                erreurs.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=valider) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(erreurs, [], f'Erreurs inattendues : {erreurs}')
        self.assertEqual(len(ventes), 2)
        self.assertEqual(ventes[0].pk, ventes[1].pk)
        self.assertEqual(Vente.objects.filter(idempotency_key=cle).count(), 1)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite, 8)
        self.assertEqual(
            MouvementStock.objects.filter(type=MouvementStock.Type.SORTIE).count(), 1
        )
        self.assertEqual(LigneVente.objects.filter(vente=ventes[0]).count(), 1)
