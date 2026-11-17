"""Services métier des ventes.

La validation d'une vente est atomique : réservation FEFO, création des
lignes, sortie de stock et création du paiement se font dans une seule
transaction. Une clé d'idempotence empêche les doubles validations.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.utils import generer_numero, journaliser
from medicaments.models import Medicament
from stock.allocation import (
    allouer_lot_choisi,
    allouer_lots_fefo,
    consommer_lots,
    reinjecter_lot,
)

from .models import LigneVente, Paiement, RetourVente, Vente


@transaction.atomic
def creer_vente(lignes, utilisateur, client=None, mode_paiement=Vente.MODE_ESPECES,
                idempotency_key=None, note=''):
    """Valide une vente, décrémente le stock et crée le paiement (RG06/RG08).

    La clé d'idempotence est vérifiée sous verrou puis protégée par la
    contrainte d'unicité dans un savepoint : en cas de double validation
    concurrente, le second appel récupère la vente du premier au lieu de
    lever une ``IntegrityError``.
    """
    if idempotency_key:
        existante = (
            Vente.objects.select_for_update()
            .filter(idempotency_key=idempotency_key)
            .first()
        )
        if existante is not None:
            return existante
    if not lignes:
        raise ValidationError('Le panier est vide.')

    lignes_validees = []
    for ligne in lignes:
        medicament = ligne['medicament']
        quantite = ligne['quantite']
        lot = ligne.get('lot')
        if quantite <= 0:
            raise ValidationError('Les quantités doivent être positives.')
        if medicament.statut != Medicament.STATUT_ACTIF:
            raise ValidationError(f'{medicament.nom} est archivé et ne peut plus être vendu.')
        if lot is not None and lot.medicament_id != medicament.pk:
            raise ValidationError("Le lot sélectionné n'appartient pas à ce médicament.")
        lignes_validees.append((medicament, quantite, lot))

    total = sum(
        (medicament.prix_vente * quantite for medicament, quantite, lot in lignes_validees),
        Decimal('0'),
    )

    for tentative in range(3):
        numero = generer_numero('VTE', Vente)
        try:
            with transaction.atomic():
                vente = Vente.objects.create(
                    numero=numero,
                    client=client,
                    utilisateur=utilisateur,
                    mode_paiement=mode_paiement,
                    total=total,
                    note=note,
                    statut=(Vente.STATUT_CONFIRMEE if mode_paiement == Vente.MODE_ESPECES
                            else Vente.STATUT_EN_ATTENTE),
                    **({'idempotency_key': idempotency_key} if idempotency_key else {}),
                )
            break
        except IntegrityError:
            # Concurrence : l'autre transaction vient de créer la même vente.
            existante = (
                Vente.objects.filter(idempotency_key=idempotency_key).first()
                if idempotency_key else None
            )
            if existante is not None:
                return existante
            if tentative == 2:
                raise
    else:
        raise ValidationError("Impossible de générer un numéro de vente unique.")

    # Les lots explicitement choisis sont traités en premier ; l'allocation
    # FEFO des autres lignes voit donc le stock déjà réduit par ces choix.
    for medicament, quantite, lot in sorted(lignes_validees, key=lambda l: l[2] is None):
        lots = (
            allouer_lot_choisi(medicament, lot, quantite)
            if lot is not None
            else allouer_lots_fefo(medicament, quantite)
        )
        for lot_alloue, quantite_allouee in lots:
            LigneVente.objects.create(
                vente=vente,
                medicament=medicament,
                lot=lot_alloue,
                numero_lot=lot_alloue.numero_lot,
                date_peremption=lot_alloue.date_peremption,
                quantite=quantite_allouee,
                prix_unitaire=medicament.prix_vente,
            )
        consommer_lots(
            lots, reference=numero, utilisateur=utilisateur, motif='Vente',
        )

    Paiement.objects.create(
        vente=vente,
        mode=mode_paiement,
        montant=total,
        statut=(Paiement.STATUT_CONFIRME if mode_paiement == Vente.MODE_ESPECES
                else Paiement.STATUT_EN_ATTENTE),
        confirme_par=utilisateur if mode_paiement == Vente.MODE_ESPECES else None,
        confirme_le=timezone.now() if mode_paiement == Vente.MODE_ESPECES else None,
    )
    journaliser(utilisateur, 'Vente validée', instance=vente, details=f'Total : {total} Ar')
    return vente


@transaction.atomic
def confirmer_paiement(paiement, reference, utilisateur):
    """Confirme un paiement électronique après vérification de son statut."""
    paiement = Paiement.objects.select_for_update().get(pk=paiement.pk)
    if paiement.statut == Paiement.STATUT_CONFIRME:
        return paiement
    paiement.statut = Paiement.STATUT_CONFIRME
    paiement.reference = reference
    paiement.confirme_par = utilisateur
    paiement.confirme_le = timezone.now()
    paiement.save()
    vente = paiement.vente
    if vente.statut != Vente.STATUT_ANNULEE:
        vente.statut = Vente.STATUT_CONFIRMEE
        vente.save(update_fields=['statut', 'modifie_le'])
    journaliser(utilisateur, 'Paiement confirmé', instance=paiement, details=reference)
    return paiement


@transaction.atomic
def creer_retour(ligne, quantite, motif, utilisateur, remettre_en_stock=True):
    """Enregistre un retour compensatoire sans supprimer la vente d'origine."""
    if quantite <= 0:
        raise ValidationError('La quantité retournée doit être positive.')
    # `lot` est une FK nullable : SELECT FOR UPDATE sur une jointure externe
    # est refusé par PostgreSQL. On verrouille uniquement la ligne de vente.
    ligne = LigneVente.objects.select_for_update().select_related(
        'vente', 'medicament'
    ).get(pk=ligne.pk)
    deja_retourne = sum(r.quantite for r in ligne.retours.all())
    if deja_retourne + quantite > ligne.quantite:
        raise ValidationError('La quantité retournée dépasse la ligne de vente.')

    lot = ligne.lot
    eligible = bool(
        lot and lot.est_delivrable and remettre_en_stock
    )
    retour = RetourVente.objects.create(
        vente=ligne.vente,
        ligne=ligne,
        medicament=ligne.medicament,
        lot=lot,
        quantite=quantite,
        motif=motif,
        montant_rembourse=ligne.prix_unitaire * quantite,
        remis_en_stock=eligible,
        utilisateur=utilisateur,
    )
    if eligible:
        reinjecter_lot(
            lot, quantite, reference=retour.vente.numero,
            utilisateur=utilisateur, motif=f'Retour : {motif}',
        )
    journaliser(utilisateur, 'Retour enregistré', instance=retour,
                details=f'{quantite} x {ligne.medicament} — {motif}')
    return retour


@transaction.atomic
def annuler_vente(vente, motif, utilisateur):
    """Annule une vente par des retours compensatoires tracés (RG10)."""
    vente = Vente.objects.select_for_update().get(pk=vente.pk)
    if vente.statut == Vente.STATUT_ANNULEE:
        raise ValidationError('Cette vente est déjà annulée.')
    for ligne in vente.lignes.all():
        deja = sum(r.quantite for r in ligne.retours.all())
        restant = ligne.quantite - deja
        if restant > 0:
            creer_retour(ligne, restant, motif, utilisateur, remettre_en_stock=True)
    vente.statut = Vente.STATUT_ANNULEE
    vente.save(update_fields=['statut', 'modifie_le'])
    for paiement in vente.paiements.all():
        if paiement.statut != Paiement.STATUT_REMBOURSE:
            paiement.statut = Paiement.STATUT_REMBOURSE
            paiement.save(update_fields=['statut'])
    journaliser(utilisateur, 'Vente annulée', instance=vente, details=motif)
    return vente
