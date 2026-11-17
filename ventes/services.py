"""Services métier des ventes.

La validation d'une vente est atomique : réservation FEFO, création des
lignes, sortie de stock et création du paiement se font dans une seule
transaction. Une clé d'idempotence empêche les doubles validations.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.utils import generer_numero, journaliser
from medicaments.models import Medicament
from stock.allocation import allouer_lots_fefo, consommer_lots, reinjecter_lot

from .models import LigneVente, Paiement, RetourVente, Vente


@transaction.atomic
def creer_vente(lignes, utilisateur, client=None, mode_paiement=Vente.MODE_ESPECES,
                idempotency_key=None, note=''):
    """Valide une vente, décrémente le stock et crée le paiement (RG06/RG08)."""
    if idempotency_key:
        existante = Vente.objects.filter(idempotency_key=idempotency_key).first()
        if existante is not None:
            return existante
    if not lignes:
        raise ValidationError('Le panier est vide.')

    quantites_par_medicament = {}
    for ligne in lignes:
        medicament = ligne['medicament']
        quantite = ligne['quantite']
        if quantite <= 0:
            raise ValidationError('Les quantités doivent être positives.')
        if medicament.statut != Medicament.STATUT_ACTIF:
            raise ValidationError(f'{medicament.nom} est archivé et ne peut plus être vendu.')
        quantites_par_medicament[medicament.pk] = (
            quantites_par_medicament.get(medicament.pk, 0) + quantite
        )

    allocations = []
    for medicament_id, quantite in quantites_par_medicament.items():
        medicament = Medicament.objects.get(pk=medicament_id)
        lots = allouer_lots_fefo(medicament, quantite)
        allocations.extend([(medicament, lot, qt) for lot, qt in lots])

    numero = generer_numero('VTE', Vente)
    total = sum(
        (medicament.prix_vente * qt for medicament, lot, qt in allocations),
        Decimal('0'),
    )

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
    for medicament, lot, quantite in allocations:
        LigneVente.objects.create(
            vente=vente,
            medicament=medicament,
            lot=lot,
            numero_lot=lot.numero_lot,
            date_peremption=lot.date_peremption,
            quantite=quantite,
            prix_unitaire=medicament.prix_vente,
        )
    consommer_lots(
        [(lot, qt) for medicament, lot, qt in allocations],
        reference=numero, utilisateur=utilisateur, motif='Vente',
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
