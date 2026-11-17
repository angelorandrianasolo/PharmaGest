"""Tests de l'interface : bouton Retour, navigation et mise en page."""

import re

from achats.services import creer_commande
from django.test import override_settings
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


class InterfaceCompleteTests(BaseTestCase):
    @staticmethod
    def _nav(contenu):
        return re.search(r'<nav class="side-nav".*?</nav>', contenu, re.S).group(0)

    def test_bouton_retour_sur_les_pages_publiques(self):
        for route in ('utilisateurs:login', 'utilisateurs:inscription',
                      'utilisateurs:inscription_ok', 'utilisateurs:password_reset',
                      'utilisateurs:password_reset_done'):
            with self.subTest(route=route):
                contenu = self.client.get(reverse(route)).content.decode()
                self.assertIn('body class="auth-page"', contenu)
                self.assertIn('class="auth-shell"', contenu)
                self.assertIn('class="btn-retour"', contenu)
                self.assertIn('data-retour', contenu)

    def test_bouton_retour_est_unique_par_page(self):
        self.client.force_login(Fabrique.utilisateur('interface-unique', 'administrateur'))
        for route in ('home', 'medicaments:liste', 'stock:lots'):
            with self.subTest(route=route):
                contenu = self.client.get(reverse(route)).content.decode()
                self.assertEqual(contenu.count('class="btn-retour"'), 1)
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse('utilisateurs:login')).content.decode()
            .count('class="btn-retour"'), 1
        )

    def test_lien_actif_de_la_navigation(self):
        self.client.force_login(Fabrique.utilisateur('interface-actif', 'administrateur'))
        cas = (
            ('home', f'<a class="nav-item-app active" href="{reverse("home")}">'),
            ('ventes:caisse', f'<a class="nav-item-app active" href="{reverse("ventes:caisse")}">'),
            ('rapports:dashboard',
             f'<a class="nav-item-app active" href="{reverse("rapports:dashboard")}">'),
        )
        for route, attendu in cas:
            with self.subTest(route=route):
                contenu = self.client.get(reverse(route)).content.decode()
                self.assertIn(attendu, contenu)

    def test_navigation_filtree_selon_le_role(self):
        self.client.force_login(Fabrique.utilisateur('interface-caissier', 'caissier'))
        nav = self._nav(self.client.get(reverse('home')).content.decode())
        self.assertNotIn('Tableau de bord', nav)
        self.assertNotIn('>Stocks</a>', nav)
        self.assertNotIn('>Achats</a>', nav)
        self.assertNotIn('Utilisateurs', nav)
        self.assertIn('>Caisse</a>', nav)
        self.assertIn('>Ventes</a>', nav)

        self.client.force_login(Fabrique.utilisateur('interface-admin', 'administrateur'))
        nav = self._nav(self.client.get(reverse('home')).content.decode())
        for libelle in ('Tableau de bord', 'Stocks', 'Achats', 'Utilisateurs'):
            with self.subTest(libelle=libelle):
                self.assertIn(libelle, nav)

        self.client.force_login(
            Fabrique.utilisateur('interface-responsable', 'responsable_gestion')
        )
        contenu = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('>Stocks</a>', self._nav(contenu))
        # La carte d'accès rapide « Stocks » reste visible, elle.
        self.assertIn(f'href="{reverse("stock:lots")}"', contenu)

    @override_settings(PHARMACIE_NOM='Pharmacie Interface Test')
    def test_carte_utilisateur_et_formulaire_de_deconnexion(self):
        utilisateur = Fabrique.utilisateur('interface-profil', 'pharmacien')
        utilisateur.first_name = 'Andry'
        utilisateur.last_name = 'Rakoto'
        utilisateur.save(update_fields=['first_name', 'last_name'])
        self.client.force_login(utilisateur)

        contenu = self.client.get(reverse('home')).content.decode()
        self.assertIn('class="user-card"', contenu)
        self.assertIn(f'class="user-card" href="{reverse("utilisateurs:profil")}"', contenu)
        self.assertIn('Andry Rakoto', contenu)
        self.assertIn('Pharmacien responsable', contenu)
        self.assertIn(f'action="{reverse("utilisateurs:logout")}"', contenu)
        self.assertIn('csrfmiddlewaretoken', contenu)
        self.assertIn('Pharmacie Interface Test', contenu)

    def test_messages_success_et_error_sont_rendus(self):
        gestion = Fabrique.utilisateur('interface-messages', 'gestionnaire_stock')
        medicament = Fabrique.medicament()
        commande = creer_commande(
            Fabrique.fournisseur(), gestion,
            [{'medicament': medicament, 'quantite': 1,
              'prix_unitaire': medicament.prix_achat}],
        )
        self.client.force_login(gestion)
        url = reverse('achats:commande_valider', args=[commande.pk])

        reponse = self.client.post(url, follow=True)
        self.assertContains(reponse, 'alert alert-success')
        self.assertContains(reponse, 'Commande validée.')
        self.assertContains(reponse, 'btn-close')

        reponse = self.client.post(url, follow=True)
        self.assertContains(reponse, 'alert alert-danger')

    def test_elements_structurels_et_script_de_retour(self):
        self.client.force_login(Fabrique.utilisateur('interface-structure', 'administrateur'))
        contenu = self.client.get(reverse('home')).content.decode()
        self.assertIn('id="menuToggle"', contenu)
        self.assertIn('aria-label="Ouvrir le menu"', contenu)
        self.assertIn('aria-expanded="false"', contenu)
        self.assertIn('id="sidebarBackdrop"', contenu)
        self.assertIn('id="i-back"', contenu)
        self.assertIn('id="i-home"', contenu)
        self.assertIn("[data-retour]", contenu)
        self.assertIn('window.history.back()', contenu)

    def test_controles_dacces_sans_page_de_base(self):
        tableau = reverse('rapports:dashboard')
        self.assertRedirects(
            self.client.get(tableau),
            f"{reverse('utilisateurs:login')}?next={tableau}",
            fetch_redirect_response=False,
        )
        self.client.force_login(Fabrique.utilisateur('interface-refus', 'inscrit'))
        reponse = self.client.get(tableau)
        self.assertEqual(reponse.status_code, 403)
        self.assertNotIn('data-retour', reponse.content.decode())

    def test_style_des_pages_dauthentification(self):
        connexion = self.client.get(reverse('utilisateurs:login')).content.decode()
        for classe in ('auth-wrap', 'auth-art', 'auth-panel'):
            self.assertIn(classe, connexion)
        for route in ('utilisateurs:inscription', 'utilisateurs:inscription_ok'):
            with self.subTest(route=route):
                contenu = self.client.get(reverse(route)).content.decode()
                self.assertIn('auth-card', contenu)
                self.assertNotIn('auth-wrap', contenu)
                self.assertNotIn('auth-panel', contenu)
