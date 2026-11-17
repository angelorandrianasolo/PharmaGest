"""Tests du catalogue : photos, recherche et archivage non destructif."""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase  # noqa: F401

from .base import BaseTestCase
from django.urls import reverse
from PIL import Image

from core.utils import valider_image
from medicaments.models import Medicament

from .factories import Fabrique


class PhotoMedicamentTests(BaseTestCase):
    def _image(self, format='PNG'):
        buffer = BytesIO()
        Image.new('RGB', (10, 10), color='blue').save(buffer, format=format)
        return SimpleUploadedFile('photo.png', buffer.getvalue(), content_type='image/png')

    def test_image_valide_est_acceptee(self):
        image = self._image()
        self.assertEqual(valider_image(image), image)

    def test_fichier_non_image_est_rejete(self):
        faux = SimpleUploadedFile('faux.png', b'ceci nest pas une image',
                                  content_type='image/png')
        with self.assertRaises(ValidationError):
            valider_image(faux)

    def test_format_non_autorise_est_rejete(self):
        buffer = BytesIO()
        Image.new('RGB', (10, 10)).save(buffer, format='BMP')
        bmp = SimpleUploadedFile('image.bmp', buffer.getvalue(), content_type='image/bmp')
        with self.assertRaises(ValidationError):
            valider_image(bmp)

    def test_image_trop_grande_est_rejetee(self):
        image = SimpleUploadedFile('gros.png', b'x' * (5 * 1024 * 1024 + 1),
                                   content_type='image/png')
        with self.assertRaises(ValidationError):
            valider_image(image)


class ArchivageMedicamentTests(BaseTestCase):
    def setUp(self):
        self.medicament = Fabrique.medicament()
        self.pharmacien = Fabrique.utilisateur('pharmacien-test', 'pharmacien')

    def test_archiver_puis_restaurer_sans_supprimer(self):
        self.client.force_login(self.pharmacien)
        url = reverse('medicaments:archiver', args=[self.medicament.pk])

        self.client.post(url)
        self.medicament.refresh_from_db()
        self.assertEqual(self.medicament.statut, Medicament.STATUT_ARCHIVE)
        self.assertTrue(Medicament.objects.filter(pk=self.medicament.pk).exists())

        self.client.post(url)
        self.medicament.refresh_from_db()
        self.assertEqual(self.medicament.statut, Medicament.STATUT_ACTIF)

    def test_recherche_par_nom_et_par_code(self):
        Fabrique.medicament(nom='Aspirine 100 mg', code='ASP-100')
        Fabrique.medicament(nom='Vitamine B12', code='VIT-B12')
        self.client.force_login(self.pharmacien)

        response = self.client.get(reverse('medicaments:liste'), {'q': 'Aspirine'})
        self.assertContains(response, 'Aspirine 100 mg')
        self.assertNotContains(response, 'Vitamine B12')

        response = self.client.get(reverse('medicaments:liste'), {'q': 'VIT-B12'})
        self.assertContains(response, 'Vitamine B12')
