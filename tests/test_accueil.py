"""Tests de la page d'accueil : photo d'accueil et activité réelle."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from medicaments.models import Medicament
from ventes.models import Paiement, Vente

from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique


class AccueilTests(BaseTestCase):
    def test_accueil_affiche_la_photo_et_un_tableau_d_activite(self):
        administrateur = Fabrique.utilisateur('admin-accueil', 'administrateur')
        self.client.force_login(administrateur)

        reponse = self.client.get(reverse('home'))
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()

        # La photo d'accueil est restaurée à côté du titre principal.
        self.assertIn('images/maquettes/couverture.jpg', contenu)
        # Le bloc « références visuelles du cahier » reste supprimé.
        self.assertNotIn('Références visuelles du cahier', contenu)
        self.assertNotIn('static/images/maquettes/tableau-de-bord.jpg', contenu)
        self.assertNotIn('static/images/maquettes/vente-caisse.jpg', contenu)
        # Le contenu professionnel est présent.
        self.assertIn('Activité récente', contenu)
        self.assertIn('Dernières ventes', contenu)
        self.assertIn('À traiter', contenu)
        self.assertIn('Alertes de stock', contenu)


class AccueilDonneesTests(BaseTestCase):
    def test_anonyme_est_redirige_vers_la_connexion(self):
        reponse = self.client.get(reverse('home'))
        self.assertRedirects(
            reponse, f"{reverse('utilisateurs:login')}?next=/",
            fetch_redirect_response=False,
        )

    def test_alertes_incluent_les_stocks_indisponibles_et_excluent_les_archives(self):
        self.client.force_login(Fabrique.utilisateur('accueil-alertes', 'administrateur'))
        disponible = Fabrique.medicament('Produit En Rupture')
        sans_lot = Fabrique.medicament('Produit Sans Lot')
        bloque = Fabrique.medicament('Produit Lot Bloque')
        Fabrique.lot(bloque, 'LOT-BLOQUE', 30, jours=100, bloque=True)
        perime = Fabrique.medicament('Produit Lot Perime')
        Fabrique.lot(perime, 'LOT-PERIME', 30, jours=-1)
        archive = Fabrique.medicament('Produit Archive')
        archive.statut = Medicament.STATUT_ARCHIVE
        archive.save(update_fields=['statut'])

        reponse = self.client.get(reverse('home'))
        noms = [medicament.nom for medicament in reponse.context['alertes']]
        self.assertIn(disponible.nom, noms)
        self.assertIn(sans_lot.nom, noms)
        # Un lot bloqué ou périmé ne compte pas comme stock délivrable.
        self.assertIn(bloque.nom, noms)
        self.assertIn(perime.nom, noms)
        self.assertNotIn(archive.nom, noms)
        self.assertContains(reponse, 'Alertes de stock')

    def test_statistiques_du_jour_avec_ventes_en_attente(self):
        admin = Fabrique.utilisateur('accueil-stats', 'administrateur')
        self.client.force_login(admin)
        Vente.objects.create(numero='VTE-ACC-1', utilisateur=admin,
                             total=Decimal('1200'), statut=Vente.STATUT_CONFIRMEE)
        Vente.objects.create(numero='VTE-ACC-2', utilisateur=admin,
                             total=Decimal('800'), statut=Vente.STATUT_EN_ATTENTE)
        hier = Vente.objects.create(numero='VTE-ACC-3', utilisateur=admin,
                                    total=Decimal('5000'), statut=Vente.STATUT_CONFIRMEE)
        Vente.objects.filter(pk=hier.pk).update(date=timezone.now() - timedelta(days=1))

        stats = self.client.get(reverse('home')).context['stats_du_jour']
        self.assertEqual(stats['ventes'], 1)
        self.assertEqual(stats['chiffre_affaires'], 1200)
        self.assertEqual(stats['en_attente'], 1)

    def test_ventes_recentes_limitees_a_cinq(self):
        admin = Fabrique.utilisateur('accueil-ventes', 'administrateur')
        self.client.force_login(admin)
        for i in range(6):
            Vente.objects.create(numero=f'VTE-REC-{i}', utilisateur=admin,
                                 total=Decimal('100'), statut=Vente.STATUT_CONFIRMEE)

        reponse = self.client.get(reverse('home'))
        self.assertEqual(len(reponse.context['ventes_recentes']), 5)
        self.assertContains(reponse, 'Dernières ventes')
        self.assertContains(reponse, reverse('ventes:detail', args=[
            reponse.context['ventes_recentes'][0].pk
        ]))

    def test_lots_a_surveiller_tries_par_date_de_peremption(self):
        self.client.force_login(Fabrique.utilisateur('accueil-lots', 'administrateur'))
        medicament = Fabrique.medicament('Produit Surveille')
        Fabrique.lot(medicament, 'LOT-J10', 4, jours=10)
        Fabrique.lot(medicament, 'LOT-J40', 4, jours=40)
        Fabrique.lot(medicament, 'LOT-J0', 4, jours=0)
        Fabrique.lot(medicament, 'LOT-VIDE', 0, jours=2)

        lots = self.client.get(reverse('home')).context['lots_a_surveiller']
        self.assertEqual([lot.numero_lot for lot in lots], ['LOT-J0', 'LOT-J10'])
        self.assertIn(reverse('medicaments:detail', args=[medicament.pk]),
                      self.client.get(reverse('home')).content.decode())

    def test_receptions_du_jour_selon_la_permission(self):
        utilisateur = Fabrique.utilisateur('accueil-receptions', 'gestionnaire_stock')
        medicament = Fabrique.medicament()
        commande = Fabrique.commande_receptionnee(medicament, utilisateur=utilisateur)
        commande.receptions.update(
            date_reception=timezone.localdate() - timedelta(days=1)
        )
        Fabrique.commande_receptionnee(
            Fabrique.medicament('Produit Recu Jour'), utilisateur=utilisateur
        )
        self.client.force_login(utilisateur)
        self.assertEqual(self.client.get(reverse('home')).context['receptions_du_jour'], 1)

        self.client.force_login(Fabrique.utilisateur('accueil-sans-reception', 'caissier'))
        self.assertNotIn('receptions_du_jour', self.client.get(reverse('home')).context)

    def test_paiements_en_attente_affiches_pour_le_caissier(self):
        caissier = Fabrique.utilisateur('accueil-paiements', 'caissier')
        vente = Vente.objects.create(numero='VTE-PAI-ACC', utilisateur=caissier,
                                     total=Decimal('300'), statut=Vente.STATUT_CONFIRMEE)
        Paiement.objects.create(vente=vente, montant=Decimal('300'),
                                statut=Paiement.STATUT_EN_ATTENTE)
        Paiement.objects.create(vente=vente, montant=Decimal('150'),
                                statut=Paiement.STATUT_CONFIRME)
        self.client.force_login(caissier)

        reponse = self.client.get(reverse('home'))
        self.assertEqual(len(reponse.context['paiements_en_attente']), 1)
        self.assertContains(reponse, 'badge bg-info')
        self.assertContains(reponse, reverse('ventes:detail', args=[vente.pk]))

    def test_navigation_et_cartes_selon_le_role(self):
        self.client.force_login(Fabrique.utilisateur('accueil-inscrit', 'inscrit'))
        reponse = self.client.get(reverse('home'))
        self.assertNotIn('stats_du_jour', reponse.context)
        self.assertNotIn('Aujourd’hui', reponse.content.decode())
        self.assertNotIn('Ouvrir la caisse', reponse.content.decode())

        self.client.force_login(Fabrique.utilisateur('accueil-caisse', 'caissier'))
        reponse = self.client.get(reverse('home'))
        self.assertIn('stats_du_jour', reponse.context)
        self.assertNotIn('receptions_du_jour', reponse.context)
        self.assertIn('Ouvrir la caisse', reponse.content.decode())

        self.client.force_login(Fabrique.utilisateur('accueil-gestion', 'gestionnaire_stock'))
        reponse = self.client.get(reverse('home'))
        self.assertIn('receptions_du_jour', reponse.context)
        self.assertNotIn('paiements_en_attente', reponse.context)
        self.assertIn('Achats', reponse.content.decode())

    def test_health_est_un_endpoint_public(self):
        reponse = self.client.get(reverse('health'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), {'statut': 'ok', 'application': 'PharmaGest'})
