"""Tests du catalogue : photos, recherche et archivage non destructif."""

from decimal import Decimal
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


class CatalogueAccesCrudTests(BaseTestCase):
    def test_acces_au_catalogue_selon_le_role(self):
        for route in ('medicaments:liste', 'medicaments:categories'):
            with self.subTest(route=route):
                url = reverse(route)
                reponse = self.client.get(url)
                self.assertRedirects(
                    reponse, f"{reverse('utilisateurs:login')}?next={url}",
                    fetch_redirect_response=False,
                )

        self.client.force_login(Fabrique.utilisateur('catalogue-caissier', 'caissier'))
        reponse = self.client.get(reverse('medicaments:liste'))
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn('Catalogue des médicaments', contenu)
        self.assertNotIn('Ajouter un médicament', contenu)
        self.assertEqual(self.client.get(reverse('medicaments:creer')).status_code, 403)

    def test_creation_dun_medicament_par_le_pharmacien(self):
        categorie = Fabrique.categorie()
        pharmacien = Fabrique.utilisateur('catalogue-pharmacien', 'pharmacien')
        self.client.force_login(pharmacien)
        reponse = self.client.post(reverse('medicaments:creer'), {
            'nom': 'Amoxicilline 500 mg',
            'denomination_generique': 'Amoxicilline',
            'categorie': categorie.pk,
            'forme': 'Gélule',
            'dosage': '500 mg',
            'laboratoire': 'Labo test',
            'code_barres': '',
            'prix_achat': '150',
            'prix_vente': '300',
            'seuil_alerte': '12',
            'statut': Medicament.STATUT_ACTIF,
        })
        self.assertRedirects(reponse, reverse('medicaments:liste'))
        medicament = Medicament.objects.get(nom='Amoxicilline 500 mg')
        self.assertEqual(medicament.cree_par, pharmacien)
        self.assertIsNone(medicament.code_barres)
        self.assertEqual(medicament.seuil_alerte, 12)

    def test_creation_invalide_sans_prix_est_refusee(self):
        categorie = Fabrique.categorie()
        self.client.force_login(Fabrique.utilisateur('catalogue-invalide', 'pharmacien'))
        reponse = self.client.post(reverse('medicaments:creer'), {
            'nom': 'Produit incomplet',
            'categorie': categorie.pk,
            'prix_achat': '0',
            'prix_vente': '-5',
            'seuil_alerte': '10',
            'statut': Medicament.STATUT_ACTIF,
        })
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context['form'].errors)
        self.assertFalse(Medicament.objects.filter(nom='Produit incomplet').exists())

    def test_modification_filtre_categorie_et_tri(self):
        pharmacien = Fabrique.utilisateur('catalogue-modif', 'pharmacien')
        self.client.force_login(pharmacien)
        medicament = Fabrique.medicament(nom='Ancien nom')
        reponse = self.client.post(
            reverse('medicaments:modifier', args=[medicament.pk]), {
                'nom': 'Nouveau nom',
                'categorie': medicament.categorie_id,
                'prix_achat': '250',
                'prix_vente': '600',
                'seuil_alerte': '10',
                'statut': Medicament.STATUT_ACTIF,
            }
        )
        self.assertRedirects(reponse, reverse('medicaments:liste'))
        medicament.refresh_from_db()
        self.assertEqual(medicament.nom, 'Nouveau nom')
        self.assertEqual(medicament.prix_vente, Decimal('600'))
        self.assertIsNone(medicament.cree_par)

        reponse = self.client.get(
            reverse('medicaments:liste'), {'categorie': medicament.categorie_id}
        )
        self.assertEqual([m.pk for m in reponse.context['medicaments']], [medicament.pk])

        reponse = self.client.get(reverse('medicaments:liste'), {'tri': 'bogus'})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context['filtres']['tri'], 'bogus')
