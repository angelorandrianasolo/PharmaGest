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
