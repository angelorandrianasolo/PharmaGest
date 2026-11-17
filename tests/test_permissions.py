"""Tests de la matrice des rôles et des permissions (RG01/RG02)."""

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase  # noqa: F401

from .base import BaseTestCase
from django.urls import reverse

from core.permissions import ADMINISTRATEUR, CAISSIER, ROLE_PERMISSIONS

from .factories import Fabrique


class RolesTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def test_groupes_crees_avec_les_bonnes_permissions(self):
        caissier = Group.objects.get(name='Caissier')
        codes = set(caissier.permissions.values_list('codename', flat=True))
        self.assertIn('add_vente', codes)
        self.assertIn('valider_vente', codes)
        self.assertNotIn('receptionner_commande', codes)
        self.assertTrue(
            set(ROLE_PERMISSIONS[CAISSIER]).issubset(codes)
        )

    def test_administrateur_a_toutes_les_permissions(self):
        admin = Group.objects.get(name='Administrateur')
        total = Permission.objects.count()
        self.assertEqual(admin.permissions.count(), total)
        self.assertEqual(ROLE_PERMISSIONS[ADMINISTRATEUR], ['*'])

    def test_synchronisation_groupes_depuis_le_role(self):
        utilisateur = Fabrique.utilisateur('sync-user', 'gestionnaire_stock')
        utilisateur.synchroniser_groupes()
        self.assertEqual(
            [g.name for g in utilisateur.groups.all()], ['Gestionnaire de stock']
        )

    def test_caissier_ne_peut_pas_acceder_aux_achats(self):
        caissier = Fabrique.utilisateur('caissier-perm', 'caissier')
        caissier.synchroniser_groupes()
        self.client.force_login(caissier)
        response = self.client.get(reverse('achats:commande_creer'))
        self.assertEqual(response.status_code, 403)

    def test_caissier_peut_ouvrir_la_caisse(self):
        caissier = Fabrique.utilisateur('caissier-caisse', 'caissier')
        caissier.synchroniser_groupes()
        self.client.force_login(caissier)
        response = self.client.get(reverse('ventes:caisse'))
        self.assertEqual(response.status_code, 200)

    def test_utilisateur_non_authentifie_est_redirige_vers_connexion(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('utilisateurs:login'), response['Location'])


class LecturePermissionsTests(BaseTestCase):
    """RG11 : les consultations sont protégées comme les écritures."""

    def setUp(self):
        self.caissier = Fabrique.utilisateur('caissier-lecture', 'caissier')
        self.client.force_login(self.caissier)

    def test_caissier_peut_consulter_ventes_clients_et_catalogue(self):
        for route in ('ventes:liste', 'clients:liste', 'medicaments:liste'):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_caissier_ne_peut_pas_consulter_les_modules_interdits(self):
        for route in (
            'fournisseurs:liste',
            'achats:liste',
            'stock:lots',
            'stock:mouvements',
            'rapports:dashboard',
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_fiche_client_est_protegee(self):
        client = Fabrique.client(nom='Client confidentiel')
        self.assertEqual(
            self.client.get(reverse('clients:detail', args=[client.pk])).status_code, 200
        )
        pharmacien = Fabrique.utilisateur('pharmacien-lecture', 'pharmacien')
        self.client.force_login(pharmacien)
        self.assertEqual(
            self.client.get(reverse('clients:detail', args=[client.pk])).status_code, 403
        )

    def test_lecture_anonyme_redirige_vers_connexion(self):
        self.client.logout()
        for route in (
            'ventes:liste', 'clients:liste', 'medicaments:liste',
            'fournisseurs:liste', 'stock:lots',
        ):
            with self.subTest(route=route):
                reponse = self.client.get(reverse(route))
                self.assertEqual(reponse.status_code, 302)
                self.assertIn(reverse('utilisateurs:login'), reponse['Location'])


class GestionComptesTests(BaseTestCase):
    """La gestion des comptes reste administrative, mais le refus est explicite."""

    def test_administrateur_peut_modifier_un_compte(self):
        admin = Fabrique.utilisateur('admin-comptes', 'administrateur')
        cible = Fabrique.utilisateur('cible-comptes', 'pharmacien')
        self.client.force_login(admin)
        url = reverse('utilisateurs:modifier', args=[cible.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        reponse = self.client.post(url, {
            'username': cible.username,
            'first_name': 'Jean',
            'last_name': cible.last_name,
            'email': cible.email,
            'telephone': cible.telephone,
            'role': cible.role,
            'is_active': 'on',
            'groups': [g.pk for g in cible.groups.all()],
            'mot_de_passe': 'testpass123',
        })
        self.assertRedirects(reponse, reverse('utilisateurs:liste'))
        cible.refresh_from_db()
        self.assertEqual(cible.first_name, 'Jean')

    def test_non_administrateur_recoit_un_refus_explicite(self):
        pharmacien = Fabrique.utilisateur('pharmacien-refus', 'pharmacien')
        cible = Fabrique.utilisateur('cible-refus', 'caissier')
        self.client.force_login(pharmacien)
        reponse = self.client.get(reverse('utilisateurs:modifier', args=[cible.pk]))
        self.assertEqual(reponse.status_code, 403)
        contenu = reponse.content.decode()
        self.assertIn('La gestion des comptes est réservée aux administrateurs', contenu)
        self.assertIn('Modifier mon profil', contenu)

    def test_bouton_modifier_masque_sans_permission(self):
        lecteur = Fabrique.utilisateur('lecteur-comptes', 'inscrit')
        lecteur.user_permissions.add(
            Permission.objects.get(codename='view_utilisateur')
        )
        cible = Fabrique.utilisateur('cible-lecture', 'caissier')
        self.client.force_login(lecteur)
        reponse = self.client.get(reverse('utilisateurs:liste'))
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn(
            reverse('utilisateurs:modifier', args=[cible.pk]),
            reponse.content.decode(),
        )

    def test_desactivation_de_son_propre_compte_reste_refusee(self):
        admin = Fabrique.utilisateur('admin-self', 'administrateur')
        self.client.force_login(admin)
        reponse = self.client.post(
            reverse('utilisateurs:basculer_actif', args=[admin.pk])
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertIn(
            'vous ne pouvez pas désactiver votre propre compte',
            reponse.content.decode().lower(),
        )
