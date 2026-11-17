"""Charge un jeu de données fictives pour les essais et la démonstration.

`python manage.py seed_demo`
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from achats.models import CommandeAchat
from achats.services import creer_commande, receptionner_commande, valider_commande
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from utilisateurs.models import Utilisateur
from ventes.models import Vente
from ventes.services import creer_vente


class Command(BaseCommand):
    help = 'Crée des données fictives (utilisateurs, médicaments, achats, ventes)'

    def handle(self, *args, **options):
        call_command('setup_roles', verbosity=0)
        self._utilisateurs()
        medicaments = self._catalogue()
        fournisseur = self._fournisseur()
        client = self._client()
        self._achats(medicaments, fournisseur)
        self._ventes(medicaments, client)
        self.stdout.write(self.style.SUCCESS('Données fictives chargées.'))

    def _utilisateurs(self):
        comptes = [
            ('admin', 'administrateur', True),
            ('pharmacien', 'pharmacien', False),
            ('stock', 'gestionnaire_stock', False),
            ('caissier', 'caissier', False),
            ('gestion', 'responsable_gestion', False),
        ]
        for username, role, superuser in comptes:
            user, created = Utilisateur.objects.get_or_create(
                username=username,
                defaults={'role': role, 'is_staff': superuser, 'is_superuser': superuser,
                          'first_name': username.capitalize()},
            )
            if created:
                user.set_password('pharma123')
                user.save()
                user.synchroniser_groupes()
        self.stdout.write('  Utilisateurs : admin / pharmacien / stock / caissier / gestion')

    def _catalogue(self):
        categories = {}
        for nom, description in [
            ('Antalgiques', 'Médicaments contre la douleur'),
            ('Antibiotiques', 'Traitements des infections bactériennes'),
            ('Antipaludiques', 'Traitements du paludisme'),
            ('Vitamines', 'Compléments alimentaires'),
        ]:
            categories[nom], _ = Categorie.objects.get_or_create(
                nom=nom, defaults={'description': description}
            )

        donnees = [
            ('Paracétamol 500 mg', 'Paracétamol', 'Comprimé', '500 mg', 'PharmaMad',
             'ANT-P500', Decimal('250'), Decimal('500'), 20),
            ('Amoxicilline 500 mg', 'Amoxicilline', 'Gélule', '500 mg', 'PharmaMad',
             'ANT-A500', Decimal('900'), Decimal('1800'), 15),
            ('Artéméther-Luméfantrine', 'Artéméther', 'Comprimé', '20/120 mg', 'PharmaMad',
             'ANT-AL20', Decimal('1200'), Decimal('2400'), 10),
            ('Vitamine C 1 g', 'Acide ascorbique', 'Comprimé effervescent', '1 g', 'VitaLab',
             'VIT-C1G', Decimal('300'), Decimal('650'), 25),
            ('Ibuprofène 400 mg', 'Ibuprofène', 'Comprimé', '400 mg', 'PharmaMad',
             'ANT-I400', Decimal('450'), Decimal('900'), 20),
        ]
        medicaments = {}
        admin = Utilisateur.objects.filter(username='admin').first()
        for (nom, generique, forme, dosage, labo, code, achat, vente, seuil) in donnees:
            categorie = categories['Antibiotiques'] if 'Amox' in nom else (
                categories['Antipaludiques'] if 'Arté' in nom else (
                    categories['Vitamines'] if 'Vitamine' in nom else categories['Antalgiques']
                )
            )
            medicament, _ = Medicament.objects.get_or_create(
                code_barres=code,
                defaults={
                    'nom': nom,
                    'denomination_generique': generique,
                    'categorie': categorie,
                    'forme': forme,
                    'dosage': dosage,
                    'laboratoire': labo,
                    'prix_achat': achat,
                    'prix_vente': vente,
                    'seuil_alerte': seuil,
                    'cree_par': admin,
                },
            )
            medicaments[code] = medicament
        self.stdout.write(f'  Catalogue : {len(medicaments)} médicaments, {len(categories)} catégories')
        return medicaments

    def _fournisseur(self):
        fournisseur, _ = Fournisseur.objects.get_or_create(
            nom='Distribution Santé Madagascar',
            defaults={
                'adresse': '12, avenue de l’Indépendance, Antananarivo',
                'telephone': '+261 34 00 000 01',
                'email': 'contact@distributionsante.mg',
                'identifiant_fiscal': 'IF-000123456',
                'contact_principal': 'Mme Rasoamanana',
                'actif': True,
            },
        )
        self.stdout.write(f'  Fournisseur : {fournisseur.nom}')
        return fournisseur

    def _client(self):
        client, _ = Client.objects.get_or_create(
            telephone='+261 34 00 000 02',
            defaults={'nom': 'Client démonstration', 'email': 'client.demo@example.mg'},
        )
        self.stdout.write(f'  Client : {client.nom}')
        return client

    def _achats(self, medicaments, fournisseur):
        if CommandeAchat.objects.filter(numero__startswith='CMD-DEMO').exists():
            self.stdout.write('  Achats : déjà présents (ignorés)')
            return
        utilisateur = Utilisateur.objects.get(username='stock')
        commande = creer_commande(
            fournisseur,
            utilisateur,
            [
                {'medicament': medicaments['ANT-P500'], 'quantite': 100,
                 'prix_unitaire': Decimal('250')},
                {'medicament': medicaments['ANT-A500'], 'quantite': 60,
                 'prix_unitaire': Decimal('900')},
                {'medicament': medicaments['ANT-AL20'], 'quantite': 40,
                 'prix_unitaire': Decimal('1200')},
                {'medicament': medicaments['VIT-C1G'], 'quantite': 80,
                 'prix_unitaire': Decimal('300')},
                {'medicament': medicaments['ANT-I400'], 'quantite': 50,
                 'prix_unitaire': Decimal('450')},
            ],
            note='Commande de démonstration',
        )
        valider_commande(commande, utilisateur)
        aujourdhui = timezone.localdate()
        receptionner_commande(
            commande,
            [
                {'medicament': medicaments['ANT-P500'], 'numero_lot': 'P500-A',
                 'date_peremption': aujourdhui + timedelta(days=400),
                 'quantite': 100, 'prix_unitaire': Decimal('250'),
                 'ligne_achat': commande.lignes.get(medicament=medicaments['ANT-P500'])},
                {'medicament': medicaments['ANT-A500'], 'numero_lot': 'A500-A',
                 'date_peremption': aujourdhui + timedelta(days=200),
                 'quantite': 60, 'prix_unitaire': Decimal('900'),
                 'ligne_achat': commande.lignes.get(medicament=medicaments['ANT-A500'])},
                {'medicament': medicaments['ANT-AL20'], 'numero_lot': 'AL20-A',
                 'date_peremption': aujourdhui + timedelta(days=25),
                 'quantite': 40, 'prix_unitaire': Decimal('1200'),
                 'ligne_achat': commande.lignes.get(medicament=medicaments['ANT-AL20'])},
                {'medicament': medicaments['VIT-C1G'], 'numero_lot': 'VC1G-A',
                 'date_peremption': aujourdhui + timedelta(days=500),
                 'quantite': 80, 'prix_unitaire': Decimal('300'),
                 'ligne_achat': commande.lignes.get(medicament=medicaments['VIT-C1G'])},
                {'medicament': medicaments['ANT-I400'], 'numero_lot': 'I400-A',
                 'date_peremption': aujourdhui + timedelta(days=350),
                 'quantite': 50, 'prix_unitaire': Decimal('450'),
                 'ligne_achat': commande.lignes.get(medicament=medicaments['ANT-I400'])},
            ],
            utilisateur,
            note='Réception de démonstration',
        )
        self.stdout.write(f'  Achats : commande {commande.numero} réceptionnée (lots créés)')

    def _ventes(self, medicaments, client):
        if Vente.objects.filter(note='Vente de démonstration').exists():
            self.stdout.write('  Ventes : déjà présentes (ignorées)')
            return
        caissier = Utilisateur.objects.get(username='caissier')
        vente = creer_vente(
            [
                {'medicament': medicaments['ANT-P500'], 'quantite': 3},
                {'medicament': medicaments['VIT-C1G'], 'quantite': 2},
            ],
            caissier,
            client=client,
            mode_paiement=Vente.MODE_ESPECES,
            note='Vente de démonstration',
        )
        creer_vente(
            [{'medicament': medicaments['ANT-A500'], 'quantite': 1}],
            caissier,
            client=client,
            mode_paiement=Vente.MODE_MOBILE_MONEY,
            note='Vente de démonstration',
        )
        self.stdout.write(f'  Ventes : {vente.numero} (espèces) + une vente mobile money en attente')
