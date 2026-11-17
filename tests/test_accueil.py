"""Test de la page d'accueil : activité réelle, sans références au cahier."""

from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique


class AccueilTests(BaseTestCase):
    def test_accueil_remplace_les_maquettes_par_un_tableau_d_activite(self):
        administrateur = Fabrique.utilisateur('admin-accueil', 'administrateur')
        self.client.force_login(administrateur)

        reponse = self.client.get(reverse('home'))
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()

        self.assertNotIn('Références visuelles du cahier', contenu)
        self.assertNotIn('static/images/maquettes/', contenu)
        self.assertIn('Activité récente', contenu)
        self.assertIn('Dernières ventes', contenu)
        self.assertIn('À traiter', contenu)
        self.assertIn('Alertes de stock', contenu)
