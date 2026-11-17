"""Tests de la page de connexion et de son formulaire."""

from django.urls import reverse

from .base import BaseTestCase
from .factories import Fabrique


class ConnexionInterfaceTests(BaseTestCase):
    def test_page_connexion_avec_formulaire_et_visuel_original(self):
        reponse = self.client.get(reverse('utilisateurs:login'))
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        # Carte éditoriale à deux panneaux : identité pharmacie et formulaire.
        for element in (
            'auth-wrap', 'auth-art', 'auth-panel', 'login-brand', 'login-story',
            'login-features', 'login-form-head', 'login-submit',
            'images/hero-pharmacie.svg', 'Stocks et lots FEFO', 'Accès par rôle',
        ):
            with self.subTest(element=element):
                self.assertIn(element, contenu)
        self.assertNotIn('social-wordmark', contenu)
        self.assertNotIn('social-avatars', contenu)
        self.assertIn('placeholder="Votre identifiant"', contenu)
        self.assertIn('placeholder="Votre mot de passe"', contenu)
        self.assertIn('Espace réservé au personnel habilité', contenu)
        self.assertIn('Mot de passe oublié', contenu)
        self.assertIn('Créer un compte', contenu)
        self.assertIn('data-retour', contenu)

    def test_nouveau_style_uniquement_sur_la_connexion(self):
        inscription = self.client.get(reverse('utilisateurs:inscription')).content.decode()
        confirmation = self.client.get(reverse('utilisateurs:inscription_ok')).content.decode()
        for contenu in (inscription, confirmation):
            self.assertIn('auth-card', contenu)
            self.assertNotIn('auth-wrap', contenu)
            self.assertNotIn('login-brand', contenu)

    def test_connexion_avec_un_compte_demo_redirige_vers_l_accueil(self):
        Fabrique.utilisateur('admin-connexion', 'administrateur')
        reponse = self.client.post(
            reverse('utilisateurs:login'),
            {'username': 'admin-connexion', 'password': 'testpass123'},
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse['Location'], reverse('home'))
