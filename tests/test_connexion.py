"""Tests de la page de connexion et de son formulaire."""

from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique


class ConnexionInterfaceTests(BaseTestCase):
    def test_page_connexion_avec_formulaire_et_visuel_original(self):
        reponse = self.client.get(reverse('utilisateurs:login'))
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        # Ancienne carte de connexion avec bandeau illustré, sans réseau social.
        self.assertIn('auth-wrap', contenu)
        self.assertIn('auth-art', contenu)
        self.assertIn('auth-panel', contenu)
        self.assertIn('images/hero-pharmacie.svg', contenu)
        self.assertNotIn('social-wordmark', contenu)
        self.assertNotIn('social-avatars', contenu)
        self.assertIn('placeholder="Votre identifiant"', contenu)
        self.assertIn('placeholder="Votre mot de passe"', contenu)
        self.assertIn('Espace réservé au personnel habilité', contenu)
        self.assertIn('Mot de passe oublié', contenu)
        self.assertIn('Créer un compte', contenu)
        self.assertIn('data-retour', contenu)

    def test_ancien_style_uniquement_sur_la_connexion(self):
        inscription = self.client.get(reverse('utilisateurs:inscription')).content.decode()
        confirmation = self.client.get(reverse('utilisateurs:inscription_ok')).content.decode()
        for contenu in (inscription, confirmation):
            self.assertIn('auth-card', contenu)
            self.assertNotIn('auth-wrap', contenu)

    def test_connexion_avec_un_compte_demo_redirige_vers_l_accueil(self):
        Fabrique.utilisateur('admin-connexion', 'administrateur')
        reponse = self.client.post(
            reverse('utilisateurs:login'),
            {'username': 'admin-connexion', 'password': 'testpass123'},
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse['Location'], reverse('home'))
