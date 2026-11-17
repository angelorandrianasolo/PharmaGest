"""Tests de la page de connexion et de son formulaire."""

from django.core import mail
from django.test import override_settings
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

    def test_champs_avec_autocompletion_et_focus_navigateur(self):
        contenu = self.client.get(reverse('utilisateurs:login')).content.decode()
        self.assertIn('autocomplete="username"', contenu)
        self.assertIn('autocomplete="current-password"', contenu)
        self.assertIn('autofocus', contenu)
        self.assertIn('class="form-control"', contenu)

    def test_connexion_avec_un_compte_demo_redirige_vers_l_accueil(self):
        Fabrique.utilisateur('admin-connexion', 'administrateur')
        reponse = self.client.post(
            reverse('utilisateurs:login'),
            {'username': 'admin-connexion', 'password': 'testpass123'},
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse['Location'], reverse('home'))

    def test_identifiants_invalides_affichent_une_erreur(self):
        Fabrique.utilisateur('user-invalide', 'caissier')
        reponse = self.client.post(
            reverse('utilisateurs:login'),
            {'username': 'user-invalide', 'password': 'mauvais-mot-de-passe'},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context['form'].errors)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_compte_inactif_ne_peut_pas_se_connecter(self):
        Fabrique.utilisateur('user-inactif', 'caissier', is_active=False)
        reponse = self.client.post(
            reverse('utilisateurs:login'),
            {'username': 'user-inactif', 'password': 'testpass123'},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context['form'].errors)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_utilisateur_deja_connecte_est_redirige_depuis_la_connexion(self):
        utilisateur = Fabrique.utilisateur('user-connecte', 'administrateur')
        self.client.force_login(utilisateur)
        reponse = self.client.get(reverse('utilisateurs:login'))
        self.assertRedirects(reponse, reverse('home'))

    def test_deconnexion_renvoie_vers_la_page_de_connexion(self):
        utilisateur = Fabrique.utilisateur('user-deconnexion', 'caissier')
        self.client.force_login(utilisateur)
        reponse = self.client.post(reverse('utilisateurs:logout'))
        self.assertRedirects(reponse, reverse('utilisateurs:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_page_protegee_redirige_l_anonyme_vers_la_connexion(self):
        cible = reverse('utilisateurs:profil')
        reponse = self.client.get(cible)
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(
            reponse['Location'], f"{reverse('utilisateurs:login')}?next={cible}"
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reinitialisation_du_mot_de_passe_envoie_un_email(self):
        utilisateur = Fabrique.utilisateur('user-reset', 'pharmacien', email='user@pharma.mg')
        reponse = self.client.get(reverse('utilisateurs:password_reset'))
        self.assertEqual(reponse.status_code, 200)
        reponse = self.client.post(
            reverse('utilisateurs:password_reset'), {'email': utilisateur.email}
        )
        self.assertRedirects(reponse, reverse('utilisateurs:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(utilisateur.email, mail.outbox[0].to)
