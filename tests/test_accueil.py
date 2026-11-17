"""Tests de la page d'accueil : photo d'accueil et activité réelle."""

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
