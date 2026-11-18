"""Tests du générateur de données de démonstration."""

from django.core.management import call_command
from django.urls import reverse

from achats.models import CommandeAchat
from medicaments.models import Medicament
from stock.services import verifier_integrite
from utilisateurs.models import Utilisateur
from ventes.models import Vente

from .base import BaseTestCase


class SeedDemoTests(BaseTestCase):
    """Le jeu de démonstration est riche, cohérent et idempotent."""

    def test_seed_cree_un_jeu_coherent(self):
        call_command('seed_demo', scale='test', verbosity=0)

        self.assertEqual(Medicament.objects.count(), 62)
        self.assertEqual(Utilisateur.objects.filter(username='demandeur').count(), 1)
        self.assertEqual(
            CommandeAchat.objects.filter(
                note__startswith='DEMO-2026-test-achats'
            ).count(),
            2,
        )
        self.assertTrue(
            Vente.objects.filter(note__startswith='DEMO-2026-test-ventes').exists()
        )
        self.assertEqual(verifier_integrite(), [])

    def test_seed_est_idempotent(self):
        call_command('seed_demo', scale='test', verbosity=0)
        comptes = (
            Medicament.objects.count(),
            CommandeAchat.objects.count(),
            Vente.objects.count(),
        )

        call_command('seed_demo', scale='test', verbosity=0)

        self.assertEqual(
            (Medicament.objects.count(), CommandeAchat.objects.count(),
             Vente.objects.count()),
            comptes,
        )

    def test_compte_en_attente_peut_etre_active_par_l_admin(self):
        call_command('seed_demo', scale='test', verbosity=0)
        demandeur = Utilisateur.objects.get(username='demandeur')
        self.assertFalse(demandeur.is_active)
        self.assertEqual(demandeur.role, 'inscrit')

        admin = Utilisateur.objects.get(username='admin')
        self.client.force_login(admin)
        reponse = self.client.post(
            reverse('utilisateurs:basculer_actif', args=[demandeur.pk])
        )
        self.assertRedirects(reponse, reverse('utilisateurs:liste'))
        demandeur.refresh_from_db()
        self.assertTrue(demandeur.is_active)
