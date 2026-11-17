"""Tests de sauvegarde et restauration (RG09)."""

import json
import re
import tempfile
from io import StringIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from core.models import JournalAudit
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.models import Utilisateur
from ventes.models import Paiement, Vente
from ventes.services import creer_vente

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


class SauvegardeCommandesTests(BaseTestCase):
    def test_export_explicite_produit_un_json_valide_avec_accents(self):
        Fabrique.medicament(nom='Médicament à accents éàü')
        with tempfile.TemporaryDirectory() as dossier:
            destination = Path(dossier) / 'sous-dossier' / 'backup.json'
            sortie = StringIO()
            chemin = call_command(
                'sauvegarder', output=str(destination), verbosity=0, stdout=sortie,
            )
            self.assertEqual(chemin, str(destination))
            self.assertTrue(destination.is_file())
            self.assertIn('Sauvegarde créée :', sortie.getvalue())
            self.assertIn(str(destination.stat().st_size), sortie.getvalue())

            donnees = json.loads(destination.read_text(encoding='utf-8'))
            self.assertTrue(all('model' in objet and 'pk' in objet for objet in donnees))
            self.assertTrue(any(
                'Médicament à accents éàü' in json.dumps(objet, ensure_ascii=False)
                for objet in donnees
            ))

    @override_settings(MEDIA_ROOT='/tmp/opencode/pharmagest-tests-media')
    def test_chemin_par_defaut_est_horodate_dans_backups(self):
        with tempfile.TemporaryDirectory() as dossier:
            with override_settings(BASE_DIR=dossier):
                chemin = call_command('sauvegarder', verbosity=0)
            self.assertEqual(Path(chemin).parent, Path(dossier) / 'backups')
            self.assertRegex(
                Path(chemin).name, r'^pharmagest-\d{8}-\d{6}\.json$'
            )
            self.assertTrue(Path(chemin).is_file())

    def test_sauvegarde_inclut_les_groupes_et_permissions(self):
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / 'roles.json'
            call_command('sauvegarder', output=str(source), verbosity=0)
            donnees = json.loads(source.read_text(encoding='utf-8'))

        modeles = {objet['model'] for objet in donnees}
        self.assertIn('auth.group', modeles)
        self.assertIn('auth.permission', modeles)
        groupes = [objet for objet in donnees if objet['model'] == 'auth.group']
        self.assertTrue(any(groupe['fields']['name'] == 'Caissier' for groupe in groupes))

    def test_sauvegarde_de_securite_contient_l_etat_avant_restauration(self):
        medicament = Fabrique.medicament(nom='État A')
        source = Path(tempfile.mkdtemp()) / 'source.json'
        call_command('sauvegarder', output=str(source), verbosity=0)

        Medicament.objects.filter(pk=medicament.pk).update(nom='État B')
        sortie = StringIO()
        call_command('restaurer', str(source), verbosity=0, stdout=sortie)
        self.assertIn('Sauvegarde de sécurité créée avant restauration.', sortie.getvalue())
        self.assertIn('Données restaurées depuis', sortie.getvalue())

        securite = source.with_suffix('.avant-restauration.json')
        self.assertTrue(securite.is_file())
        self.assertIn('État B', securite.read_text(encoding='utf-8'))
        medicament.refresh_from_db()
        self.assertEqual(medicament.nom, 'État A')

    def test_fichier_source_introuvable_est_refuse(self):
        with tempfile.TemporaryDirectory() as dossier:
            absent = Path(dossier) / 'absent.json'
            with self.assertRaises(CommandError) as contexte:
                call_command('restaurer', str(absent), verbosity=0)
            self.assertIn('Fichier introuvable', str(contexte.exception))
            self.assertFalse(absent.with_suffix('.avant-restauration.json').exists())

    def test_restauration_invalide_ne_modifie_pas_les_donnees(self):
        medicament = Fabrique.medicament(nom='Donnée préexistante')
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / 'invalide.json'
            source.write_text('[{"model":', encoding='utf-8')
            with self.assertRaises(Exception):
                call_command('restaurer', str(source), verbosity=0)

            medicament.refresh_from_db()
            self.assertEqual(medicament.nom, 'Donnée préexistante')
            self.assertTrue(source.with_suffix('.avant-restauration.json').exists())

    def test_restaurer_deux_fois_ne_cree_pas_de_doublons(self):
        utilisateur = Fabrique.utilisateur('backup-idempotent', 'caissier')
        medicament = Fabrique.medicament()
        categorie = medicament.categorie
        source = Path(tempfile.mkdtemp()) / 'idempotent.json'
        call_command('sauvegarder', output=str(source), verbosity=0)
        Medicament.objects.all().delete()

        for _ in range(2):
            call_command('restaurer', str(source), verbosity=0)

        self.assertEqual(Medicament.objects.count(), 1)
        self.assertEqual(Medicament.objects.get().categorie, categorie)
        self.assertTrue(Utilisateur.objects.filter(pk=utilisateur.pk).exists())

    def test_couverture_multi_modeles_et_relations(self):
        utilisateur = Fabrique.utilisateur('backup-multi', 'administrateur')
        medicament = Fabrique.medicament(nom='Produit Multi')
        Fabrique.lot(medicament, 'LOT-MULTI', 6, jours=90)
        vente = creer_vente([{'medicament': medicament, 'quantite': 2}], utilisateur)
        Paiement.objects.create(vente=vente, montant=vente.total,
                                statut=Paiement.STATUT_CONFIRME)
        JournalAudit.objects.create(action='Test sauvegarde', modele='test')
        source = Path(tempfile.mkdtemp()) / 'multi.json'
        call_command('sauvegarder', output=str(source), verbosity=0)

        Paiement.objects.all().delete()
        vente.lignes.all().delete()
        Vente.objects.all().delete()
        MouvementStock.objects.all().delete()
        LotStock.objects.all().delete()
        Medicament.objects.all().delete()
        Categorie.objects.all().delete()
        JournalAudit.objects.all().delete()

        call_command('restaurer', str(source), verbosity=0)

        restaure = Medicament.objects.get(nom='Produit Multi')
        self.assertEqual(restaure.categorie.nom, 'Antalgiques')
        # 6 unités reçues moins 2 délivrées par la vente figurant dans la sauvegarde.
        self.assertEqual(restaure.lots.get(numero_lot='LOT-MULTI').quantite, 4)
        self.assertEqual(Vente.objects.count(), 1)
        # creer_vente génère son propre paiement, plus celui créé explicitement.
        self.assertEqual(Paiement.objects.count(), 2)
        self.assertEqual(JournalAudit.objects.filter(action='Test sauvegarde').count(), 1)
        # Une entrée de stock (lot) et une sortie (vente).
        self.assertEqual(MouvementStock.objects.count(), 2)

    @override_settings(MEDIA_ROOT='/tmp/opencode/pharmagest-tests-media')
    def test_sauvegarde_json_ne_transporte_pas_le_binaire_des_photos(self):
        utilisateur = Fabrique.utilisateur('backup-photo', 'pharmacien')
        with tempfile.TemporaryDirectory() as dossier:
            with override_settings(MEDIA_ROOT=dossier):
                utilisateur.photo.save('photo-test.png',
                                       ContentFile(b'contenu-binaire'), save=True)
                nom_photo = utilisateur.photo.name
                photo = Path(dossier) / nom_photo
                self.assertTrue(photo.is_file())
                source = Path(dossier) / 'photo.json'
                call_command('sauvegarder', output=str(source), verbosity=0)

                photo.unlink()
                Utilisateur.objects.filter(pk=utilisateur.pk).update(photo='')
                call_command('restaurer', str(source), verbosity=0)

                self.assertEqual(
                    Utilisateur.objects.get(pk=utilisateur.pk).photo.name, nom_photo
                )
                self.assertFalse(photo.exists())
