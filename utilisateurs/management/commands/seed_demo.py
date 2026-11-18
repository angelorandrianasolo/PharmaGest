"""Charge un jeu de données fictives pour les essais et la démonstration.

`python manage.py seed_demo`                 → jeu complet
`python manage.py seed_demo --scale test`    → petit jeu (tests rapides)

Le remplissage est déterministe et idempotent : les objets sont identifiés par
des clés stables (codes-barres, numéros de téléphone, notes marquées). Relancer
la commande avec la même échelle ne duplique rien.
"""

from datetime import timedelta
from decimal import Decimal
import random

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from django.utils import timezone

from achats.models import CommandeAchat
from achats.services import creer_commande, receptionner_commande, valider_commande
from clients.models import Client
from core.models import JournalAudit
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from stock.services import corriger_quantite
from utilisateurs.models import Utilisateur
from ventes.models import Paiement, RetourVente, Vente
from ventes.services import annuler_vente, confirmer_paiement, creer_retour, creer_vente


MARCHEUR = 'DEMO-2026'
ECHELLES = {
    'normal': {'clients': 60, 'commandes': 30, 'ventes': 260},
    'test': {'clients': 3, 'commandes': 2, 'ventes': 4},
}

CATEGORIES = [
    ('Antalgiques', 'Médicaments contre la douleur et la fièvre'),
    ('Antibiotiques', 'Traitements des infections bactériennes'),
    ('Antipaludiques', 'Traitements et prophylaxie du paludisme'),
    ('Vitamines', 'Vitamines, oligo-éléments et compléments'),
    ('Antihypertensifs', 'Traitements de l’hypertension artérielle'),
    ('Antidiabétiques', 'Traitements du diabète'),
    ('Respiratoires', 'Traitements des voies respiratoires'),
    ('Digestifs', 'Traitements gastro-intestinaux'),
    ('Antifongiques', 'Traitements des infections fongiques'),
    ('Ophtalmologie', 'Collyres et pommades ophtalmiques'),
    ('Pédiatrie', 'Formes adaptées aux enfants'),
    ('Dermatologie', 'Traitements cutanés et antiseptiques'),
    ('Urgences', 'Médicaments d’urgence et injectables'),
    ('Toniques', 'Fortifiants et compléments énergétiques'),
]

# (nom, générique, catégorie, forme, dosage, laboratoire, achat, vente, seuil, code)
MEDICAMENTS = [
    ('Paracétamol 500 mg', 'Paracétamol', 'Antalgiques', 'Comprimé', '500 mg', 'PharmaMad',
     Decimal('250'), Decimal('500'), 20, 'ANT-P500'),
    ('Amoxicilline 500 mg', 'Amoxicilline', 'Antibiotiques', 'Gélule', '500 mg', 'PharmaMad',
     Decimal('900'), Decimal('1800'), 15, 'ANT-A500'),
    ('Artéméther-Luméfantrine', 'Artéméther', 'Antipaludiques', 'Comprimé', '20/120 mg', 'PharmaMad',
     Decimal('1200'), Decimal('2400'), 10, 'ANT-AL20'),
    ('Vitamine C 1 g', 'Acide ascorbique', 'Vitamines', 'Comprimé effervescent', '1 g', 'VitaLab',
     Decimal('300'), Decimal('650'), 25, 'VIT-C1G'),
    ('Ibuprofène 400 mg', 'Ibuprofène', 'Antalgiques', 'Comprimé', '400 mg', 'PharmaMad',
     Decimal('450'), Decimal('900'), 20, 'ANT-I400'),
    ('Diclofénac 50 mg', 'Diclofénac', 'Antalgiques', 'Comprimé', '50 mg', 'PharmaMad',
     Decimal('400'), Decimal('800'), 20, None),
    ('Aspirine 100 mg', 'Acide acétylsalicylique', 'Antalgiques', 'Comprimé', '100 mg', 'VitaLab',
     Decimal('180'), Decimal('400'), 30, None),
    ('Paracétamol sirop', 'Paracétamol', 'Pédiatrie', 'Sirop', '125 mg/5 ml', 'PharmaMad',
     Decimal('350'), Decimal('750'), 15, None),
    ('Tramadol 50 mg', 'Tramadol', 'Antalgiques', 'Gélule', '50 mg', 'MedPharma',
     Decimal('1100'), Decimal('2200'), 10, None),
    ('Naproxène 500 mg', 'Naproxène', 'Antalgiques', 'Comprimé', '500 mg', 'PharmaMad',
     Decimal('600'), Decimal('1200'), 15, None),
    ('Ampicilline 500 mg', 'Ampicilline', 'Antibiotiques', 'Gélule', '500 mg', 'PharmaMad',
     Decimal('800'), Decimal('1600'), 15, None),
    ('Ciprofloxacine 500 mg', 'Ciprofloxacine', 'Antibiotiques', 'Comprimé', '500 mg', 'MedPharma',
     Decimal('1200'), Decimal('2400'), 12, None),
    ('Azithromycine 250 mg', 'Azithromycine', 'Antibiotiques', 'Comprimé', '250 mg', 'MedPharma',
     Decimal('1500'), Decimal('3000'), 10, None),
    ('Cotrimoxazole 480 mg', 'Sulfaméthoxazole/Triméthoprime', 'Antibiotiques', 'Comprimé',
     '480 mg', 'PharmaMad', Decimal('500'), Decimal('1000'), 20, None),
    ('Gentamicine 80 mg', 'Gentamicine', 'Antibiotiques', 'Injectable', '80 mg/2 ml', 'MedPharma',
     Decimal('900'), Decimal('1800'), 10, None),
    ('Métronidazole 500 mg', 'Métronidazole', 'Antibiotiques', 'Comprimé', '500 mg', 'PharmaMad',
     Decimal('450'), Decimal('900'), 20, None),
    ('Ceftriaxone 1 g', 'Ceftriaxone', 'Antibiotiques', 'Injectable', '1 g', 'MedPharma',
     Decimal('2200'), Decimal('4400'), 8, None),
    ('Chloroquine 150 mg', 'Chloroquine', 'Antipaludiques', 'Comprimé', '150 mg', 'PharmaMad',
     Decimal('300'), Decimal('650'), 20, None),
    ('Sulfadoxine-Pyriméthamine', 'Sulfadoxine/Pyriméthamine', 'Antipaludiques', 'Comprimé',
     '500/25 mg', 'PharmaMad', Decimal('800'), Decimal('1600'), 15, None),
    ('Quinine 300 mg', 'Quinine', 'Antipaludiques', 'Comprimé', '300 mg', 'MedPharma',
     Decimal('1000'), Decimal('2000'), 12, None),
    ('Artésunate 60 mg', 'Artésunate', 'Antipaludiques', 'Injectable', '60 mg', 'MedPharma',
     Decimal('1800'), Decimal('3600'), 8, None),
    ('Vitamine A 200 000 UI', 'Rétinol', 'Vitamines', 'Capsule', '200 000 UI', 'VitaLab',
     Decimal('350'), Decimal('750'), 20, None),
    ('Vitamine D3 1000 UI', 'Cholécalciférol', 'Vitamines', 'Comprimé', '1000 UI', 'VitaLab',
     Decimal('500'), Decimal('1100'), 20, None),
    ('Vitamine B12 1000 µg', 'Cyanocobalamine', 'Vitamines', 'Comprimé', '1000 µg', 'VitaLab',
     Decimal('700'), Decimal('1500'), 15, None),
    ('Complexe B', 'Vitamines B', 'Vitamines', 'Comprimé', 'Complexe', 'VitaLab',
     Decimal('600'), Decimal('1300'), 20, None),
    ('Fer + Acide folique', 'Fer/folate', 'Vitamines', 'Comprimé', '60 mg/400 µg', 'VitaLab',
     Decimal('400'), Decimal('900'), 25, None),
    ('Amlodipine 5 mg', 'Amlodipine', 'Antihypertensifs', 'Comprimé', '5 mg', 'CardioLab',
     Decimal('550'), Decimal('1100'), 20, None),
    ('Losartan 50 mg', 'Losartan', 'Antihypertensifs', 'Comprimé', '50 mg', 'CardioLab',
     Decimal('900'), Decimal('1800'), 15, None),
    ('Captopril 25 mg', 'Captopril', 'Antihypertensifs', 'Comprimé', '25 mg', 'CardioLab',
     Decimal('450'), Decimal('950'), 20, None),
    ('Hydrochlorothiazide 25 mg', 'Hydrochlorothiazide', 'Antihypertensifs', 'Comprimé',
     '25 mg', 'CardioLab', Decimal('350'), Decimal('750'), 25, None),
    ('Aténolol 50 mg', 'Aténolol', 'Antihypertensifs', 'Comprimé', '50 mg', 'CardioLab',
     Decimal('500'), Decimal('1000'), 20, None),
    ('Metformine 500 mg', 'Metformine', 'Antidiabétiques', 'Comprimé', '500 mg', 'DiabetaLab',
     Decimal('450'), Decimal('950'), 25, None),
    ('Glibenclamide 5 mg', 'Glibenclamide', 'Antidiabétiques', 'Comprimé', '5 mg', 'DiabetaLab',
     Decimal('400'), Decimal('850'), 20, None),
    ('Insuline humaine', 'Insuline', 'Antidiabétiques', 'Injectable', '100 UI/ml', 'DiabetaLab',
     Decimal('4500'), Decimal('9000'), 5, None),
    ('Salbutamol 100 µg', 'Salbutamol', 'Respiratoires', 'Inhalateur', '100 µg/dose', 'PneumoLab',
     Decimal('1800'), Decimal('3600'), 10, None),
    ('Bromhexine 8 mg', 'Bromhexine', 'Respiratoires', 'Comprimé', '8 mg', 'PneumoLab',
     Decimal('300'), Decimal('650'), 20, None),
    ('Dextrométhorphane', 'Dextrométhorphane', 'Respiratoires', 'Sirop', '15 mg/5 ml', 'PneumoLab',
     Decimal('400'), Decimal('850'), 20, None),
    ('Théophylline 200 mg', 'Théophylline', 'Respiratoires', 'Comprimé', '200 mg', 'PneumoLab',
     Decimal('550'), Decimal('1150'), 15, None),
    ('Oméprazole 20 mg', 'Oméprazole', 'Digestifs', 'Gélule', '20 mg', 'DigestLab',
     Decimal('800'), Decimal('1700'), 15, None),
    ('Ranitidine 150 mg', 'Ranitidine', 'Digestifs', 'Comprimé', '150 mg', 'DigestLab',
     Decimal('450'), Decimal('950'), 20, None),
    ('Métoclopramide 10 mg', 'Métoclopramide', 'Digestifs', 'Comprimé', '10 mg', 'DigestLab',
     Decimal('350'), Decimal('750'), 20, None),
    ('Lopéramide 2 mg', 'Lopéramide', 'Digestifs', 'Gélule', '2 mg', 'DigestLab',
     Decimal('300'), Decimal('650'), 25, None),
    ('Sulfate de magnésium', 'Magnésium sulfate', 'Digestifs', 'Poudre', '500 g', 'DigestLab',
     Decimal('1200'), Decimal('2500'), 10, None),
    ('Fluconazole 150 mg', 'Fluconazole', 'Antifongiques', 'Gélule', '150 mg', 'DermLab',
     Decimal('1200'), Decimal('2500'), 12, None),
    ('Nystatine 100 000 UI', 'Nystatine', 'Antifongiques', 'Comprimé', '100 000 UI', 'DermLab',
     Decimal('500'), Decimal('1100'), 20, None),
    ('Terbinafine 250 mg', 'Terbinafine', 'Antifongiques', 'Comprimé', '250 mg', 'DermLab',
     Decimal('900'), Decimal('1900'), 15, None),
    ('Miconazole crème', 'Miconazole', 'Antifongiques', 'Crème', '2 %', 'DermLab',
     Decimal('700'), Decimal('1500'), 20, None),
    ('Collyre chloramphénicol', 'Chloramphénicol', 'Ophtalmologie', 'Collyre', '0,5 %', 'OphtaLab',
     Decimal('600'), Decimal('1300'), 15, None),
    ('Collyre timolol', 'Timolol', 'Ophtalmologie', 'Collyre', '0,5 %', 'OphtaLab',
     Decimal('1400'), Decimal('2900'), 10, None),
    ('Pommade tétracycline', 'Tétracycline', 'Ophtalmologie', 'Pommade', '1 %', 'OphtaLab',
     Decimal('750'), Decimal('1600'), 15, None),
    ('Paracétamol nourrisson', 'Paracétamol', 'Pédiatrie', 'Suppositoire', '80 mg', 'PharmaMad',
     Decimal('250'), Decimal('550'), 20, None),
    ('Amoxicilline sirop', 'Amoxicilline', 'Pédiatrie', 'Sirop', '250 mg/5 ml', 'PharmaMad',
     Decimal('650'), Decimal('1400'), 15, None),
    ('Vitamine A sirop', 'Rétinol', 'Pédiatrie', 'Sirop', '100 000 UI/5 ml', 'VitaLab',
     Decimal('400'), Decimal('850'), 20, None),
    ('Sels de réhydratation', 'Sels oraux', 'Pédiatrie', 'Poudre', '20 g', 'PharmaMad',
     Decimal('250'), Decimal('550'), 30, None),
    ('Hydrocortisone crème', 'Hydrocortisone', 'Dermatologie', 'Crème', '1 %', 'DermLab',
     Decimal('600'), Decimal('1300'), 20, None),
    ('Bétadine solution', 'Povidone-iode', 'Dermatologie', 'Solution', '10 %', 'DermLab',
     Decimal('900'), Decimal('1900'), 15, None),
    ('Perméthrine crème', 'Perméthrine', 'Dermatologie', 'Crème', '5 %', 'DermLab',
     Decimal('800'), Decimal('1700'), 15, None),
    ('Adrénaline 1 mg', 'Épinéphrine', 'Urgences', 'Injectable', '1 mg/ml', 'UrgenceLab',
     Decimal('2200'), Decimal('4500'), 8, None),
    ('Atropine 1 mg', 'Atropine', 'Urgences', 'Injectable', '1 mg/ml', 'UrgenceLab',
     Decimal('1200'), Decimal('2500'), 10, None),
    ('Dexaméthasone 4 mg', 'Dexaméthasone', 'Urgences', 'Injectable', '4 mg/ml', 'UrgenceLab',
     Decimal('700'), Decimal('1500'), 15, None),
    ('Ginseng + Vitamines', 'Ginseng', 'Toniques', 'Comprimé', 'Complexe', 'VitaLab',
     Decimal('1000'), Decimal('2200'), 15, None),
    ('Sirop tonique fer', 'Fer', 'Toniques', 'Sirop', '100 mg/5 ml', 'VitaLab',
     Decimal('450'), Decimal('950'), 20, None),
]

FOURNISSEURS = [
    ('Distribution Santé Madagascar', '12, avenue de l’Indépendance, Antananarivo',
     '+261 34 00 000 01', 'contact@distributionsante.mg', 'IF-000123456', 'Mme Rasoamanana', True),
    ('PharmaMad Diffusion', 'Zone industrielle, Antananarivo', '+261 34 00 000 11',
     'ventes@pharmamad.mg', 'IF-000123457', 'M. Andrianjaka', True),
    ('VitaLab Madagascar', '45, rue de la Production, Antananarivo', '+261 34 00 000 12',
     'export@vitalab.mg', 'IF-000123458', 'Mme Razafindralambo', True),
    ('MedPharma Import', 'Port duties, Toamasina', '+261 34 00 000 13',
     'import@medpharma.mg', 'IF-000123459', 'M. Rasolofomanana', True),
    ('CardioLab SA', '8, avenue de la Liberté, Antananarivo', '+261 34 00 000 14',
     'contact@cardiolab.mg', 'IF-000123460', 'Dr Randrianirina', True),
    ('Diabeta Distribution', 'Lot II B 27, Antananarivo', '+261 34 00 000 15',
     'INFO@diabetadist.mg', 'IF-000123461', 'Mme Ranaivosoa', True),
    ('Ophta & Derm SARL', '23, rue des Écoles, Antananarivo', '+261 34 00 000 16',
     'contact@ophtaderm.mg', 'IF-000123462', 'Dr Razafitrimo', True),
    ('Urgence Medical Supply', 'Aéroport, Antananarivo', '+261 34 00 000 17',
     'logistique@urgencemed.mg', 'IF-000123463', 'M. Rakotondraibe', False),
    ('Laboratoire National du Médicament', 'Ambohidahy, Antananarivo', '+261 34 00 000 18',
     'lnm@lnm.mg', 'IF-000123464', 'Mme Rasoamananjara', True),
]

PRENOMS = [
    'Rakoto', 'Rasoa', 'Rabe', 'Randriamana', 'Rasoamanana', 'Ranaivoson', 'Andriana',
    'Hery', 'Miora', 'Nirina', 'Fanja', 'Sitraka', 'Tiana', 'Tojo', 'Aina', 'Lala',
    'Bodo', 'Mbola', 'Rindra', 'Fetison',
]
NOMS = [
    'Rakotomalala', 'Ramanana', 'Razafindrakoto', 'Randrianasolo', 'Rasolofomanana',
    'Andriantsitohaina', 'Ranaivosoa', 'Rabeharisoa', 'Rakotondrazaka', 'Razafindrabe',
]
MOTIFS_RETOUR = [
    'Erreur de délivrance', 'Produit non conforme', 'Changement de prescription',
    'Client insatisfait', 'Défaut d’emballage',
]


class Command(BaseCommand):
    help = 'Crée un jeu de données fictives complet (catalogue, achats, stocks, ventes)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scale', choices=sorted(ECHELLES), default='normal',
            help='Taille du jeu généré (normal : démonstration, test : rapide).',
        )

    def handle(self, *args, **options):
        echelle = options['scale']
        objectifs = ECHELLES[echelle]
        self.rng = random.Random(20261118)
        call_command('setup_roles', verbosity=0)

        utilisateurs = self._utilisateurs()
        categories = self._categories()
        medicaments = self._catalogue(categories, utilisateurs['admin'])
        fournisseurs = self._fournisseurs()
        clients = self._clients(objectifs['clients'])

        if self._deja_present(CommandeAchat, 'achats', echelle):
            self.stdout.write('  Achats : déjà présents (ignorés)')
        else:
            self._achats(medicaments, fournisseurs, utilisateurs, echelle,
                         objectifs['commandes'])

        if self._deja_present(Vente, 'ventes', echelle):
            self.stdout.write('  Ventes : déjà présentes (ignorées)')
        else:
            self._ventes(medicaments, clients, utilisateurs, echelle,
                         objectifs['ventes'])

        self._resume(echelle)

    # ------------------------------------------------------------------ outils

    def _deja_present(self, modele, bloc, echelle):
        return modele.objects.filter(
            note__startswith=f'{MARCHEUR}-{echelle}-{bloc}'
        ).exists()

    def _note(self, bloc, echelle, *parts):
        return ' '.join((f'{MARCHEUR}-{echelle}-{bloc}', *parts))

    # -------------------------------------------------------------- référentiel

    def _utilisateurs(self):
        comptes = [
            ('admin', 'administrateur', True, True),
            ('pharmacien', 'pharmacien', False, True),
            ('stock', 'gestionnaire_stock', False, True),
            ('caissier', 'caissier', False, True),
            ('gestion', 'responsable_gestion', False, True),
            ('pharmacien2', 'pharmacien', False, True),
            ('stock2', 'gestionnaire_stock', False, True),
            ('caissier2', 'caissier', False, True),
            ('demandeur', 'inscrit', False, False),  # inscription en attente
        ]
        resultat = {}
        for username, role, superuser, actif in comptes:
            user, created = Utilisateur.objects.get_or_create(
                username=username,
                defaults={
                    'role': role,
                    'is_staff': superuser,
                    'is_superuser': superuser,
                    'is_active': actif,
                    'first_name': username.capitalize(),
                    'last_name': 'Démonstration',
                    'email': f'{username}@pharmacie.mg',
                },
            )
            if created:
                user.set_password('pharma123')
                user.save()
                user.synchroniser_groupes()
            resultat[username] = user
        self.stdout.write(f'  Utilisateurs : {len(comptes)} comptes de démonstration')
        return resultat

    def _categories(self):
        categories = {}
        for nom, description in CATEGORIES:
            categories[nom], _ = Categorie.objects.get_or_create(
                nom=nom, defaults={'description': description}
            )
        self.stdout.write(f'  Catalogue : {len(categories)} catégories')
        return categories

    def _catalogue(self, categories, admin):
        medicaments = []
        for index, donnee in enumerate(MEDICAMENTS, start=1):
            (nom, generique, categorie, forme, dosage, labo, achat, vente, seuil, code) = donnee
            code = code or f'DEMO-M{index:03d}'
            medicament, _ = Medicament.objects.get_or_create(
                code_barres=code,
                defaults={
                    'nom': nom,
                    'denomination_generique': generique,
                    'categorie': categories[categorie],
                    'forme': forme,
                    'dosage': dosage,
                    'laboratoire': labo,
                    'prix_achat': achat,
                    'prix_vente': vente,
                    'seuil_alerte': seuil,
                    'cree_par': admin,
                },
            )
            medicaments.append(medicament)
        self.stdout.write(f'  Catalogue : {len(medicaments)} médicaments')
        return medicaments

    def _fournisseurs(self):
        fournisseurs = []
        for nom, adresse, telephone, email, fiscal, contact, actif in FOURNISSEURS:
            fournisseur, _ = Fournisseur.objects.get_or_create(
                nom=nom,
                defaults={
                    'adresse': adresse,
                    'telephone': telephone,
                    'email': email,
                    'identifiant_fiscal': fiscal,
                    'contact_principal': contact,
                    'actif': actif,
                },
            )
            fournisseurs.append(fournisseur)
        self.stdout.write(f'  Fournisseurs : {len(fournisseurs)}')
        return fournisseurs

    def _clients(self, objectif):
        clients = []
        for index in range(objectif):
            prenom = PRENOMS[index % len(PRENOMS)]
            nom = NOMS[(index * 7) % len(NOMS)]
            telephone = f'+261 34 {10 + index // 100:02d} {index % 100:02d} {index:03d}'
            client, _ = Client.objects.get_or_create(
                telephone=telephone,
                defaults={
                    'nom': f'{prenom} {nom}',
                    'email': f'client{index + 1:03d}@exemple.mg',
                    'adresse': f'Lot {index + 1}, Antananarivo',
                    'actif': index % 17 != 0,
                },
            )
            clients.append(client)
        self.stdout.write(f'  Clients : {len(clients)}')
        return clients

    # ------------------------------------------------------------------ achats

    def _achats(self, medicaments, fournisseurs, utilisateurs, echelle, objectif):
        stock = utilisateurs['stock']
        actifs = [f for f in fournisseurs if f.actif] or fournisseurs
        for index in range(objectif):
            fournisseur = actifs[index % len(actifs)]
            lignes = []
            for j, medicament in enumerate(self.rng.sample(medicaments, self.rng.randint(3, 6))):
                lignes.append({
                    'medicament': medicament,
                    'quantite': self.rng.randint(40, 160),
                    'prix_unitaire': medicament.prix_achat,
                })
            commande = creer_commande(
                fournisseur, stock, lignes,
                note=self._note('achats', echelle, f'commande {index + 1:03d}'),
            )
            valider_commande(commande, stock)
            self._receptionner(commande, lignes, stock, echelle, index, 0,
                               partiel=index % 7 == 0)
            if index % 7 == 0:
                self._receptionner(commande, lignes, stock, echelle, index, 1,
                                   partiel=True)

        self._incidents_stock(medicaments, utilisateurs, echelle)
        self.stdout.write(
            f'  Achats : {CommandeAchat.objects.filter(note__startswith=f"{MARCHEUR}-{echelle}-achats").count()} '
            'commandes réceptionnées'
        )

    def _receptionner(self, commande, lignes, utilisateur, echelle, index, vague,
                      partiel=False):
        aujourdhui = timezone.localdate()
        lots = []
        for j, ligne in enumerate(lignes):
            quantite = ligne['quantite'] // 2 if partiel else ligne['quantite']
            if vague == 1:
                quantite = ligne['quantite'] - quantite
            if quantite <= 0:
                continue
            sous_lots = 2 if (index + j) % 3 == 0 else 1
            premier = quantite // sous_lots
            for k in range(sous_lots):
                quantite_lot = premier if k < sous_lots - 1 else quantite - premier * (sous_lots - 1)
                lots.append({
                    'medicament': ligne['medicament'],
                    'numero_lot': f'DEMO-{index + 1:03d}-{j + 1:02d}-{vague}-{k + 1}',
                    'date_peremption': aujourdhui + timedelta(days=self.rng.randint(120, 900)),
                    'quantite': quantite_lot,
                    'prix_unitaire': ligne['prix_unitaire'],
                    'ligne_achat': commande.lignes.get(medicament=ligne['medicament']),
                })
        if lots:
            receptionner_commande(
                commande, lots, utilisateur,
                note=self._note('achats', echelle, f'réception {index + 1:03d}.{vague}'),
            )

    def _incidents_stock(self, medicaments, utilisateurs, echelle):
        stock = utilisateurs['stock']
        lots = list(LotStock.objects.filter(reference__startswith='REC-').order_by('-id')[:12])
        for lot in lots[:2]:
            lot.est_bloque = True
            lot.motif_blocage = 'Blocage démonstration — contrôle qualité en attente'
            lot.save(update_fields=['est_bloque', 'motif_blocage', 'modifie_le'])
        for lot in lots[2:7]:
            ecart = self.rng.choice([-2, -1, 1, 2])
            nouvelle = max(0, lot.quantite + ecart)
            if nouvelle != lot.quantite:
                corriger_quantite(
                    lot, nouvelle, motif='Inventaire de démonstration',
                    utilisateur=stock, reference=f'INV-DEMO-{lot.pk}',
                )

    # ------------------------------------------------------------------ ventes

    def _ventes(self, medicaments, clients, utilisateurs, echelle, objectif):
        caissier = utilisateurs['caissier']
        pharmacien = utilisateurs['pharmacien']
        par_id = {medicament.pk: medicament for medicament in medicaments}
        disponible = self._quantites_disponibles()
        ventes = []

        for index in range(objectif):
            if index % 25 == 0:
                disponible = self._quantites_disponibles()
            candidats = [
                par_id[pk] for pk, quantite in disponible.items()
                if quantite > 5 and pk in par_id
            ]
            if not candidats:
                break
            lignes = []
            for medicament in self.rng.sample(
                candidats, min(self.rng.randint(1, 4), len(candidats))
            ):
                reste = disponible.get(medicament.pk, 0) - 2
                if reste <= 0:
                    continue
                quantite = min(self.rng.randint(1, 5), reste)
                lignes.append({'medicament': medicament, 'quantite': quantite})
                disponible[medicament.pk] = reste - quantite
            if not lignes:
                continue

            client = self.rng.choice(clients + [None, None])
            tirage = self.rng.random()
            mode = (Vente.MODE_ESPECES if tirage < 0.7 else
                    Vente.MODE_MOBILE_MONEY if tirage < 0.9 else Vente.MODE_AUTRE)
            vente = creer_vente(
                lignes, caissier, client=client, mode_paiement=mode,
                note=self._note('ventes', echelle, f'vente {index + 1:04d}'),
            )
            self._dater_vente(vente, echelle, index)
            ventes.append(vente)

            if mode != Vente.MODE_ESPECES and self.rng.random() < 0.6:
                paiement = vente.paiements.first()
                if paiement:
                    confirmer_paiement(
                        paiement, f'DEMO-PAY-{index + 1:04d}', pharmacien
                    )

        self._retours_et_annulations(ventes, pharmacien, echelle)
        total = Vente.objects.filter(
            note__startswith=f'{MARCHEUR}-{echelle}-ventes'
        ).count()
        self.stdout.write(f'  Ventes : {total}')

    def _quantites_disponibles(self):
        return dict(
            LotStock.objects.filter(est_bloque=False, quantite__gt=0)
            .values_list('medicament_id')
            .annotate(total=Sum('quantite'))
            .values_list('medicament_id', 'total')
        )

    def _dater_vente(self, vente, echelle, index):
        date = timezone.now() - timedelta(
            days=self.rng.randint(0, 179),
            hours=self.rng.randint(0, 23),
            minutes=self.rng.randint(0, 59),
        )
        reference = vente.numero
        Vente.objects.filter(pk=vente.pk).update(date=date)
        Paiement.objects.filter(vente=vente).update(cree_le=date, modifie_le=date)
        MouvementStock.objects.filter(reference=reference).update(date=date)
        JournalAudit.objects.filter(
            action='Vente validée', modele='vente', objet_id=str(vente.pk)
        ).update(date=date)

    def _retours_et_annulations(self, ventes, pharmacien, echelle):
        retournes = 0
        annulees = 0
        for index, vente in enumerate(ventes):
            if vente.statut == Vente.STATUT_ANNULEE:
                continue
            ligne = vente.lignes.first()
            if ligne is None:
                continue
            if index % 13 == 0:
                try:
                    annuler_vente(vente, 'Annulation démonstration', pharmacien)
                    annulees += 1
                    continue
                except ValidationError:
                    pass
            if index % 9 == 0 and ligne.quantite > 1:
                try:
                    creer_retour(
                        ligne, 1, self.rng.choice(MOTIFS_RETOUR), pharmacien,
                        remettre_en_stock=True,
                    )
                    retournes += 1
                except ValidationError:
                    pass
        self.stdout.write(
            f'  Retours et annulations : {retournes} retours partiels, {annulees} annulations'
        )

    def _resume(self, echelle):
        prefixe_achats = f'{MARCHEUR}-{echelle}-achats'
        prefixe_ventes = f'{MARCHEUR}-{echelle}-ventes'
        commandes = CommandeAchat.objects.filter(note__startswith=prefixe_achats).count()
        ventes = Vente.objects.filter(note__startswith=prefixe_ventes).count()
        self.stdout.write(self.style.SUCCESS(
            f'Données fictives chargées ({echelle}) : '
            f'{Medicament.objects.count()} médicaments, {commandes} commandes, '
            f'{LotStock.objects.count()} lots, {ventes} ventes, '
            f'{RetourVente.objects.count()} retours, '
            f'{MouvementStock.objects.count()} mouvements, '
            f'{JournalAudit.objects.count()} entrées de journal.'
        ))
