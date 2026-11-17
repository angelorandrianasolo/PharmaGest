"""Tests de la page de connexion et de son formulaire."""

from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique


class ConnexionInterfaceTests(BaseTestCase):
    def test_page_connexion_avec_formulaire_et_visuel_original(self):
        reponse = self.client.get(reverse('utilisateurs:login'))
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn('images/hero-pharmacie.svg', contenu)
        self.assertIn('placeholder="Votre identifiant"', contenu)
        self.assertIn('placeholder="Votre mot de passe"', contenu)
        self.assertIn('Espace réservé au personnel habilité', contenu)
        self.assertIn('Mot de passe oublié', contenu)
        self.assertIn('Créer un compte', contenu)
        self.assertIn('data-retour', contenu)
        # Le formulaire est centré dans une carte étroite.
        self.assertIn('auth-wrap', contenu)

    def test_connexion_avec_un_compte_demo_redirige_vers_l_accueil(self):
        Fabrique.utilisateur('admin-connexion', 'administrateur')
        reponse = self.client.post(
            reverse('utilisateurs:login'),
            {'username': 'admin-connexion', 'password': 'testpass123'},
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse['Location'], reverse('home'))
