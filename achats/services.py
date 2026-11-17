"""Services métier des achats.

La commande ne modifie jamais le stock : seule la réception validée
augmente les quantités, une seule fois, dans une transaction atomique.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.utils import generer_numero, journaliser
from stock.services import enregistrer_reception

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


@transaction.atomic
def creer_commande(fournisseur, utilisateur, lignes, note=''):
    """Crée une commande en brouillon avec ses lignes."""
    if not lignes:
        raise ValidationError('Une commande doit contenir au moins une ligne.')
    commande = CommandeAchat.objects.create(
        numero=generer_numero('CMD', CommandeAchat),
        fournisseur=fournisseur,
        note=note,
        cree_par=utilisateur,
    )
    for ligne in lignes:
        if ligne['quantite'] <= 0:
            raise ValidationError('Les quantités commandées doivent être positives.')
        LigneAchat.objects.create(
            commande=commande,
            medicament=ligne['medicament'],
            quantite=ligne['quantite'],
            prix_unitaire=ligne['prix_unitaire'],
        )
    journaliser(utilisateur, 'Commande créée', instance=commande)
    return commande


@transaction.atomic
def valider_commande(commande, utilisateur):
    """Passe une commande du statut Brouillon à Commandée."""
    commande = CommandeAchat.objects.select_for_update().get(pk=commande.pk)
    if commande.statut != CommandeAchat.STATUT_BROUILLON:
        raise ValidationError('Seule une commande en brouillon peut être validée.')
    commande.statut = CommandeAchat.STATUT_COMMANDEE
    commande.save(update_fields=['statut', 'modifie_le'])
    journaliser(utilisateur, 'Commande validée', instance=commande)
    return commande


@transaction.atomic
def annuler_commande(commande, utilisateur):
    """Annule une commande non réceptionnée (opération tracée)."""
    commande = CommandeAchat.objects.select_for_update().get(pk=commande.pk)
    if commande.receptions.exists():
        raise ValidationError('Une commande déjà réceptionnée ne peut pas être annulée.')
    commande.statut = CommandeAchat.STATUT_ANNULEE
    commande.save(update_fields=['statut', 'modifie_le'])
    journaliser(utilisateur, 'Commande annulée', instance=commande)
    return commande


@transaction.atomic
def receptionner_commande(commande, lignes, utilisateur, note=''):
    """Enregistre une réception partielle ou totale et crée les lots (RG04/RG05).

    `lignes` : liste de dictionnaires avec medicament, numero_lot,
    date_peremption, quantite, prix_unitaire et éventuellement ligne_achat.
    """
    commande = CommandeAchat.objects.select_for_update().get(pk=commande.pk)
    if commande.statut in (
        CommandeAchat.STATUT_ANNULEE, CommandeAchat.STATUT_TOTALE
    ):
        raise ValidationError('Cette commande ne peut plus être réceptionnée.')
    if not lignes:
        raise ValidationError('Une réception doit contenir au moins une ligne.')

    nouvelles_quantites = {}
    for ligne in lignes:
        if ligne['quantite'] <= 0:
            raise ValidationError('Les quantités réceptionnées doivent être positives.')
        if ligne['date_peremption'] <= timezone.localdate():
            raise ValidationError('Un lot périmé ne peut pas être réceptionné.')
        cle = ligne['medicament'].pk
        nouvelles_quantites[cle] = nouvelles_quantites.get(cle, 0) + ligne['quantite']

    for ligne in commande.lignes.all():
        deja = sum(
            r.quantite for r in LigneReception.objects.filter(
                ligne_achat=ligne
            )
        )
        prevu = nouvelles_quantites.get(ligne.medicament_id, 0)
        if deja + prevu > ligne.quantite:
            raise ValidationError(
                f'Réception supérieure à la quantité commandée pour {ligne.medicament}.'
            )

    reception = ReceptionAchat.objects.create(
        numero=generer_numero('REC', ReceptionAchat),
        commande=commande,
        note=note,
        cree_par=utilisateur,
    )
    for ligne in lignes:
        ligne_reception = LigneReception.objects.create(
            reception=reception,
            ligne_achat=ligne.get('ligne_achat'),
            medicament=ligne['medicament'],
            numero_lot=ligne['numero_lot'],
            date_peremption=ligne['date_peremption'],
            quantite=ligne['quantite'],
            prix_unitaire=ligne['prix_unitaire'],
        )
        enregistrer_reception(
            medicament=ligne['medicament'],
            numero_lot=ligne['numero_lot'],
            date_peremption=ligne['date_peremption'],
            quantite=ligne['quantite'],
            prix_achat=ligne['prix_unitaire'],
            fournisseur=commande.fournisseur,
            ligne_reception=ligne_reception,
            reference=reception.numero,
            utilisateur=utilisateur,
        )

    if commande.quantite_receptionnee >= commande.quantite_commandee:
        commande.statut = CommandeAchat.STATUT_TOTALE
    else:
        commande.statut = CommandeAchat.STATUT_PARTIELLE
    commande.save(update_fields=['statut', 'modifie_le'])
    journaliser(utilisateur, 'Réception validée', instance=reception, request=None)
    return reception
