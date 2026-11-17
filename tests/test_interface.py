"""Test du bouton Retour disponible sur toutes les pages."""

from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique


class BoutonRetourTests(BaseTestCase):
    def test_bouton_retour_present_sur_les_pages_connectees(self):
        utilisateur = Fabrique.utilisateur('admin-interface', 'administrateur')
        self.client.force_login(utilisateur)
        for route in ('home', 'ventes:caisse', 'medicaments:liste', 'stock:lots'):
            with self.subTest(route=route):
                contenu = self.client.get(reverse(route)).content.decode()
                self.assertIn('data-retour', contenu)
                self.assertIn('> Retour', contenu)
