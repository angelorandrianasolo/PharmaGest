"""Test de bout en bout sauvegarde / restauration."""

from django.core.management import call_command
from django.test import override_settings

from medicaments.models import Medicament

from .base import BaseTestCase
from .factories import Fabrique


class SauvegardeTests(BaseTestCase):
    @override_settings(MEDIA_ROOT='/tmp/opencode/pharmagest-tests-media')
    def test_restaurer_une_sauvegarde_recupere_les_donnees(self):
        medicament = Fabrique.medicament(nom='Médicament à restaurer')
        chemin = call_command('sauvegarder', verbosity=0)

        Medicament.objects.filter(pk=medicament.pk).delete()
        self.assertFalse(Medicament.objects.filter(pk=medicament.pk).exists())

        call_command('restaurer', chemin, verbosity=0)

        restaure = Medicament.objects.get(pk=medicament.pk)
        self.assertEqual(restaure.nom, 'Médicament à restaurer')
        self.assertEqual(restaure.prix_vente, medicament.prix_vente)
