"""Tests de l'inscription publique et de la gestion du profil."""

import io

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from core.permissions import INSCRIT
from utilisateurs.models import Utilisateur

from .base import BaseTestCase
from .factories import Fabrique


class InscriptionTests(BaseTestCase):
    @override_settings(INSCRIPTION_ACTIVATION_AUTO=False)
    def test_inscription_cree_un_compte_inactif_a_activer(self):
        reponse = self.client.post(
            reverse('utilisateurs:inscription'),
            {
                'username': 'nouveau-compte',
                'first_name': 'Marie',
                'last_name': 'Rakoto',
                'email': 'marie@pharmacie.mg',
                'telephone': '032 00 000 00',
                'password1': 'MotDePasseSécurisé123!',
                'password2': 'MotDePasseSécurisé123!',
            },
        )
        self.assertRedirects(reponse, reverse('utilisateurs:inscription_ok'))
        utilisateur = Utilisateur.objects.get(username='nouveau-compte')
        self.assertFalse(utilisateur.is_active)
        self.assertEqual(utilisateur.role, INSCRIT)
        self.assertEqual(utilisateur.email, 'marie@pharmacie.mg')
        self.assertTrue(
            utilisateur.groups.filter(name='Utilisateur inscrit').exists()
        )

    @override_settings(INSCRIPTION_ACTIVATION_AUTO=False)
    def test_compte_inscrit_ne_peut_pas_se_connecter_avant_activation(self):
        self.client.post(
            reverse('utilisateurs:inscription'),
            {
                'username': 'visiteur',
                'first_name': 'Jean',
                'last_name': 'Doe',
                'email': 'jean@example.mg',
                'password1': 'MotDePasseSécurisé123!',
                'password2': 'MotDePasseSécurisé123!',
            },
        )
        connexion = self.client.post(
            reverse('utilisateurs:login'),
            {'username': 'visiteur', 'password': 'MotDePasseSécurisé123!'},
        )
        self.assertEqual(connexion.status_code, 200)
        self.assertFalse(connexion.wsgi_request.user.is_authenticated)

    def test_page_inscription_est_publique(self):
        reponse = self.client.get(reverse('utilisateurs:inscription'))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('Inscription', reponse.content.decode())


class ProfilTests(BaseTestCase):
    def setUp(self):
        self.utilisateur = Fabrique.utilisateur(
            'profil-user', 'pharmacien', email='ancien@example.mg'
        )
        self.client.force_login(self.utilisateur)

    def test_anonyme_est_redirige_vers_connexion(self):
        self.client.logout()
        for route in ('utilisateurs:profil', 'utilisateurs:profil_modifier', 'home'):
            with self.subTest(route=route):
                reponse = self.client.get(reverse(route))
                self.assertEqual(reponse.status_code, 302)
                self.assertIn(reverse('utilisateurs:login'), reponse['Location'])

    def test_profil_affiche_les_informations_du_compte(self):
        reponse = self.client.get(reverse('utilisateurs:profil'))
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        for valeur in (
            'profil-user', 'ancien@example.mg', 'Pharmacien responsable',
            'Mot de passe', 'Changer le mot de passe',
        ):
            with self.subTest(valeur=valeur):
                self.assertIn(valeur, contenu)

    def test_modification_profil_sans_confirmation_est_refusee(self):
        reponse = self.client.post(
            reverse('utilisateurs:profil_modifier'),
            {
                'first_name': 'Nouveau',
                'last_name': 'Nom',
                'email': 'nouveau@example.mg',
                'telephone': '',
                'mot_de_passe': 'mauvais-mot-de-passe',
            },
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('Le mot de passe saisi est incorrect.', reponse.content.decode())
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.first_name, '')

    def test_modification_profil_avec_confirmation_est_enregistree(self):
        reponse = self.client.post(
            reverse('utilisateurs:profil_modifier'),
            {
                'first_name': 'Nouveau',
                'last_name': 'Nom',
                'email': 'nouveau@example.mg',
                'telephone': '032 12 345 67',
                'mot_de_passe': 'testpass123',
            },
        )
        self.assertRedirects(reponse, reverse('utilisateurs:profil'))
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.first_name, 'Nouveau')
        self.assertEqual(self.utilisateur.email, 'nouveau@example.mg')

    def test_ajout_photo_avec_confirmation(self):
        tampon = io.BytesIO()
        Image.new('RGB', (16, 16), color=(20, 90, 75)).save(tampon, format='PNG')
        image = SimpleUploadedFile(
            'portrait.png', tampon.getvalue(), content_type='image/png'
        )
        reponse = self.client.post(
            reverse('utilisateurs:profil_modifier'),
            {
                'first_name': '', 'last_name': '', 'email': '', 'telephone': '',
                'photo': image, 'mot_de_passe': 'testpass123',
            },
        )
        self.assertRedirects(reponse, reverse('utilisateurs:profil'))
        self.utilisateur.refresh_from_db()
        self.assertTrue(self.utilisateur.photo.name.startswith('profils/'))

    def test_suppression_photo_sans_confirmation_est_refusee(self):
        self.utilisateur.photo = 'profils/portrait.png'
        self.utilisateur.save(update_fields=['photo'])
        reponse = self.client.post(
            reverse('utilisateurs:photo_supprimer'), {'mot_de_passe': 'incorrect'}
        )
        self.assertRedirects(reponse, reverse('utilisateurs:profil'))
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.photo.name, 'profils/portrait.png')

    def test_suppression_photo_avec_confirmation(self):
        self.utilisateur.photo = 'profils/portrait.png'
        self.utilisateur.save(update_fields=['photo'])
        reponse = self.client.post(
            reverse('utilisateurs:photo_supprimer'), {'mot_de_passe': 'testpass123'}
        )
        self.assertRedirects(reponse, reverse('utilisateurs:profil'))
        self.utilisateur.refresh_from_db()
        self.assertFalse(self.utilisateur.photo)
