"""Fabriques de données minimales pour les tests métier."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from achats.models import CommandeAchat
from achats.services import creer_commande, receptionner_commande, valider_commande
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.models import Utilisateur


class Fabrique:
    """Crée des objets valides avec des valeurs par défaut prévisibles."""

    @staticmethod
    def utilisateur(username='test-user', role='caissier', **kwargs):
        utilisateur = Utilisateur.objects.create_user(
            username=username, password='testpass123', role=role, **kwargs
        )
        utilisateur.synchroniser_groupes()
        return utilisateur

    @staticmethod
    def categorie(nom='Antalgiques'):
        categorie, _ = Categorie.objects.get_or_create(nom=nom)
        return categorie

    @staticmethod
    def medicament(nom='Paracétamol 500 mg', prix_achat='250', prix_vente='500',
                   seuil=10, code=None):
        return Medicament.objects.create(
            nom=nom,
            categorie=Fabrique.categorie(),
            prix_achat=Decimal(prix_achat),
            prix_vente=Decimal(prix_vente),
            seuil_alerte=seuil,
            code_barres=code,
        )

    @staticmethod
    def fournisseur(nom='Fournisseur test'):
        return Fournisseur.objects.create(nom=nom)

    @staticmethod
    def client(nom='Client test'):
        return Client.objects.create(nom=nom)

    @staticmethod
    def lot(medicament, numero='LOT-1', quantite=20, jours=365, bloque=False):
        lot = LotStock.objects.create(
            medicament=medicament,
            numero_lot=numero,
            date_peremption=timezone.localdate() + timedelta(days=jours),
            quantite=quantite,
            quantite_initiale=quantite,
            prix_achat=Decimal('250'),
            est_bloque=bloque,
        )
        # Un lot réel provient toujours d'une réception : on trace l'entrée
        # initiale pour que le contrôle d'intégrité reste valide.
        MouvementStock.objects.create(
            medicament=medicament,
            lot=lot,
            type=MouvementStock.Type.ENTREE,
            quantite=quantite,
            motif='Lot de test',
        )
        return lot

    @staticmethod
    def commande_receptionnee(medicament, quantite=20, utilisateur=None,
                              jours=365, numero_lot='LOT-REC'):
        """Crée une commande validée puis réceptionnée : seul chemin légal vers le stock."""
        fournisseur = Fabrique.fournisseur()
        commande = creer_commande(
            fournisseur, utilisateur or Fabrique.utilisateur('achat-user', 'gestionnaire_stock'),
            [{'medicament': medicament, 'quantite': quantite,
              'prix_unitaire': medicament.prix_achat}],
        )
        valider_commande(commande, utilisateur or commande.cree_par)
        ligne = commande.lignes.get(medicament=medicament)
        receptionner_commande(
            commande,
            [{
                'ligne_achat': ligne,
                'medicament': medicament,
                'numero_lot': numero_lot,
                'date_peremption': timezone.localdate() + timedelta(days=jours),
                'quantite': quantite,
                'prix_unitaire': medicament.prix_achat,
            }],
            utilisateur or commande.cree_par,
        )
        return commande
