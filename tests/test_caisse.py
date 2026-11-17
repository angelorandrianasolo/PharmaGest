"""Tests de la caisse interactive : recherche, lots choisis et interface."""

import uuid
from decimal import Decimal

from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique
from ventes.models import Vente


class CaisseTests(BaseTestCase):
    def setUp(self):
        self.medicament = Fabrique.medicament(
            nom='Ibuprofène 400 mg', prix_vente='800', code='1234567890123'
        )
        self.caissier = Fabrique.utilisateur('caissier-caisse-test', 'caissier')
        self.lot_proche = Fabrique.lot(self.medicament, 'LOT-PROCHE', 8, jours=30)
        self.lot_lointain = Fabrique.lot(self.medicament, 'LOT-LOIN', 12, jours=200)
        self.client.force_login(self.caissier)

    def test_recherche_par_nom_et_scan_du_code_barres(self):
        url = reverse('ventes:recherche_produit')
        reponse = self.client.get(url, {'q': 'ibuprof'})
        self.assertEqual(reponse.status_code, 200)
        resultats = reponse.json()['resultats']
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['nom'], 'Ibuprofène 400 mg')
        self.assertEqual(resultats[0]['prix'], '800.00')
        self.assertEqual(resultats[0]['lots'][0]['numero'], 'LOT-PROCHE')
        self.assertTrue(resultats[0]['lots'][0]['suggere'])

        scan = self.client.get(url, {'q': '1234567890123'})
        self.assertEqual(
            [item['id'] for item in scan.json()['resultats']], [self.medicament.pk]
        )

    def test_recherche_reservee_aux_caissiers(self):
        gestion = Fabrique.utilisateur('gestion-recherche', 'responsable_gestion')
        self.client.force_login(gestion)
        reponse = self.client.get(reverse('ventes:recherche_produit'), {'q': 'ibu'})
        self.assertEqual(reponse.status_code, 403)

    def test_lot_choisi_dans_la_caisse_est_celui_consomme(self):
        cle = uuid.uuid4()
        reponse = self.client.post(reverse('ventes:caisse'), {
            'idempotency_key': str(cle),
            'client': '',
            'mode_paiement': Vente.MODE_ESPECES,
            'note': '',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-medicament': str(self.medicament.pk),
            'form-0-quantite': '3',
            'form-0-lot': str(self.lot_lointain.pk),
        })
        self.assertEqual(reponse.status_code, 302)
        vente = Vente.objects.get(idempotency_key=cle)
        self.assertEqual(vente.lignes.get().numero_lot, 'LOT-LOIN')
        self.assertEqual(vente.total, Decimal('2400'))
        self.lot_proche.refresh_from_db()
        self.lot_lointain.refresh_from_db()
        self.assertEqual(self.lot_proche.quantite, 8)
        self.assertEqual(self.lot_lointain.quantite, 9)

    def test_sans_choix_de_lot_l_allocation_fefo_s_applique(self):
        cle = uuid.uuid4()
        reponse = self.client.post(reverse('ventes:caisse'), {
            'idempotency_key': str(cle),
            'client': '',
            'mode_paiement': Vente.MODE_ESPECES,
            'note': '',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-medicament': str(self.medicament.pk),
            'form-0-quantite': '2',
            'form-0-lot': '',
        })
        self.assertEqual(reponse.status_code, 302)
        vente = Vente.objects.get(idempotency_key=cle)
        self.assertEqual(vente.lignes.get().numero_lot, 'LOT-PROCHE')

    def test_interface_caisse_affiche_recherche_panier_et_total(self):
        contenu = self.client.get(reverse('ventes:caisse')).content.decode()
        self.assertIn('id="recherche-produit"', contenu)
        self.assertIn('id="panier-lignes"', contenu)
        self.assertIn('id="total-panier"', contenu)
        self.assertIn('data-action="plus"', contenu)

    def test_fiche_vente_propose_impression_du_recu(self):
        vente = Vente.objects.create(
            numero='VTE-TEST-0001', utilisateur=self.caissier, total=Decimal('800'),
            statut=Vente.STATUT_CONFIRMEE,
        )
        contenu = self.client.get(reverse('ventes:detail', args=[vente.pk])).content.decode()
        self.assertIn('id="imprimer-recu"', contenu)
        self.assertIn('Imprimer le reçu', contenu)

    def test_recherche_par_identifiant_du_medicament(self):
        reponse = self.client.get(
            reverse('ventes:recherche_produit'), {'id': str(self.medicament.pk)}
        )
        resultats = reponse.json()['resultats']
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['id'], self.medicament.pk)

    def test_recherche_trop_courte_ne_retourne_rien(self):
        for recherche in ('', 'i'):
            with self.subTest(recherche=recherche):
                reponse = self.client.get(
                    reverse('ventes:recherche_produit'), {'q': recherche}
                )
                self.assertEqual(reponse.json()['resultats'], [])

    def test_recherche_exclut_les_lots_perimes_et_bloques(self):
        Fabrique.lot(self.medicament, 'LOT-PERIME', 5, jours=-2)
        Fabrique.lot(self.medicament, 'LOT-BLOQUE', 5, jours=300, bloque=True)
        reponse = self.client.get(reverse('ventes:recherche_produit'), {'q': 'ibu'})
        lots = reponse.json()['resultats'][0]['lots']
        self.assertEqual(
            [lot['numero'] for lot in lots], ['LOT-PROCHE', 'LOT-LOIN']
        )

    def test_panier_est_restitue_apres_une_erreur_de_vente(self):
        reponse = self.client.post(reverse('ventes:caisse'), {
            'idempotency_key': str(uuid.uuid4()),
            'client': '',
            'mode_paiement': Vente.MODE_ESPECES,
            'note': '',
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-medicament': str(self.medicament.pk),
            'form-0-quantite': '999',
            'form-0-lot': '',
        })
        self.assertEqual(reponse.status_code, 200)
        panier = reponse.context['panier_initial']
        self.assertEqual(len(panier), 1)
        self.assertEqual(panier[0]['id'], self.medicament.pk)
        self.assertEqual(panier[0]['quantite'], '999')
