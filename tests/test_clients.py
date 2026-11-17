"""Tests de la gestion des clients : accès, CRUD, recherche et historique."""

from decimal import Decimal

from django.contrib.messages import get_messages
from django.urls import NoReverseMatch, reverse

from core.models import JournalAudit
from ventes.models import Vente

from .base import BaseTestCase
from .factories import Fabrique
from clients.models import Client


class ClientAccessTests(BaseTestCase):
    def test_acces_a_la_liste_selon_le_role(self):
        liste = reverse('clients:liste')
        reponse = self.client.get(liste)
        self.assertRedirects(
            reponse, f"{reverse('utilisateurs:login')}?next={liste}",
            fetch_redirect_response=False,
        )
        self.client.force_login(Fabrique.utilisateur('client-pharmacien', 'pharmacien'))
        self.assertEqual(self.client.get(liste).status_code, 403)
        self.client.force_login(Fabrique.utilisateur('client-gestion', 'gestionnaire_stock'))
        self.assertEqual(self.client.get(liste).status_code, 403)
        self.client.force_login(Fabrique.utilisateur('client-caissier', 'caissier'))
        self.assertEqual(self.client.get(liste).status_code, 200)
        self.client.force_login(Fabrique.utilisateur('client-resp', 'responsable_gestion'))
        self.assertEqual(self.client.get(liste).status_code, 200)

    def test_actions_visibles_selon_les_permissions(self):
        Fabrique.client('Client Action')
        self.client.force_login(Fabrique.utilisateur('client-actions-caisse', 'caissier'))
        contenu = self.client.get(reverse('clients:liste')).content.decode()
        self.assertIn('Nouveau client', contenu)
        # Le caissier peut créer mais pas modifier (pas de change_client).
        self.assertNotIn('>Modifier</a>', contenu)

        self.client.force_login(Fabrique.utilisateur('client-actions-resp', 'responsable_gestion'))
        contenu = self.client.get(reverse('clients:liste')).content.decode()
        self.assertIn('Clients', contenu)
        self.assertNotIn('Nouveau client', contenu)

    def test_recherche_par_nom_et_par_telephone(self):
        Client.objects.create(nom='Rakoto Rasoa', telephone='032 11 22 33')
        Fabrique.client('Autre Personne')
        self.client.force_login(Fabrique.utilisateur('client-recherche', 'caissier'))

        reponse = self.client.get(reverse('clients:liste'), {'q': 'rakoto'})
        self.assertEqual([c.nom for c in reponse.context['clients']], ['Rakoto Rasoa'])
        reponse = self.client.get(reverse('clients:liste'), {'q': '11 22'})
        self.assertEqual([c.nom for c in reponse.context['clients']], ['Rakoto Rasoa'])

    def test_pagination_de_la_liste(self):
        for i in range(21):
            Fabrique.client(f'Client {i:02d}')
        self.client.force_login(Fabrique.utilisateur('client-page', 'caissier'))

        reponse = self.client.get(reverse('clients:liste'))
        self.assertTrue(reponse.context['is_paginated'])
        self.assertEqual(len(reponse.context['clients']), 20)
        self.assertContains(reponse, 'Page 1 / 2')
        self.assertContains(reponse, 'Suivant')
        self.assertEqual(len(self.client.get(
            reverse('clients:liste'), {'page': 2}
        ).context['clients']), 1)

    def test_proprietes_du_modele_et_representation(self):
        client = Fabrique.client('Jean Dupont')
        self.assertEqual(str(client), 'Jean Dupont')
        self.assertEqual(client.nombre_ventes, 0)
        self.assertTrue(client.actif)

        anonyme = Client.objects.create(nom='   ')
        self.assertEqual(str(anonyme), f'Client #{anonyme.pk}')
        self.client.force_login(Fabrique.utilisateur('client-str', 'caissier'))
        contenu = self.client.get(reverse('clients:liste')).content.decode()
        self.assertIn(f'Client #{anonyme.pk}', contenu)

    def test_aucune_ecriture_daudit_ni_message_lors_du_crud(self):
        caissier = Fabrique.utilisateur('client-sans-effet', 'caissier')
        self.client.force_login(caissier)
        reponse = self.client.post(reverse('clients:creer'), {'nom': 'Client Propre'})
        self.assertEqual(list(get_messages(reponse.wsgi_request)), [])
        self.assertFalse(JournalAudit.objects.exists())
        with self.assertRaises(NoReverseMatch):
            reverse('clients:supprimer')


class ClientCrudTests(BaseTestCase):
    def setUp(self):
        self.caissier = Fabrique.utilisateur('client-crud', 'caissier')
        self.client.force_login(self.caissier)

    def test_creation_avec_champs_minimaux(self):
        reponse = self.client.post(reverse('clients:creer'), {
            'nom': 'Nouveau Client', 'telephone': '032 00 00 00', 'actif': 'on',
        })
        self.assertRedirects(reponse, reverse('clients:liste'))
        client = Client.objects.get(nom='Nouveau Client')
        self.assertTrue(client.actif)
        self.assertEqual(client.telephone, '032 00 00 00')

    def test_creation_avec_email_invalide_est_refusee(self):
        reponse = self.client.post(reverse('clients:creer'), {
            'nom': 'Client Invalide', 'email': 'pas-un-email',
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('email', reponse.context['form'].errors)
        self.assertFalse(Client.objects.filter(nom='Client Invalide').exists())

    def test_modification_par_l_admin_et_refus_aux_autres_roles(self):
        client = Fabrique.client('Ancien Client')
        url = reverse('clients:modifier', args=[client.pk])
        self.client.force_login(Fabrique.utilisateur('client-admin-modif', 'administrateur'))
        reponse = self.client.post(url, {
            'nom': 'Client Modifié', 'telephone': '032 99 99 99', 'actif': 'on',
        })
        self.assertRedirects(reponse, reverse('clients:liste'))
        client.refresh_from_db()
        self.assertEqual(client.nom, 'Client Modifié')

        # Le caissier et le responsable n'ont pas la permission change_client.
        self.client.force_login(Fabrique.utilisateur('client-refus-caisse', 'caissier'))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(Fabrique.utilisateur('client-refus-resp', 'responsable_gestion'))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_detail_avec_historique_des_ventes(self):
        client = Fabrique.client('Client Ventes')
        Vente.objects.create(
            numero='VTE-CLI-1', client=client, utilisateur=self.caissier,
            total=Decimal('1200'), statut=Vente.STATUT_CONFIRMEE,
        )
        reponse = self.client.get(reverse('clients:detail', args=[client.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Historique des ventes')
        self.assertContains(reponse, 'VTE-CLI-1')
        self.assertContains(reponse, reverse('ventes:detail', args=[
            Vente.objects.get(numero='VTE-CLI-1').pk
        ]))
        self.assertEqual(len(reponse.context['ventes']), 1)
        self.assertEqual(client.nombre_ventes, 1)
        self.assertEqual(self.client.get(
            reverse('clients:detail', args=[99999])
        ).status_code, 404)

    def test_detail_affiche_une_client_sans_nom(self):
        client = Client.objects.create(nom='', telephone='032 55 55 55')
        reponse = self.client.get(reverse('clients:detail', args=[client.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, f'Client #{client.pk}')
        self.assertContains(reponse, 'Historique des ventes')
