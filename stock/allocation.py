"""Allocation FEFO et variations liees aux ventes et retours.

FEFO = First Expired, First Out : les lots dont la peremption est la plus
proche sont consommes en priorite, sous reserve d'etre delivrables.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .exceptions import LotNonDelivrableError, StockInsuffisantError
from .models import LotStock, MouvementStock
from .services import enregistrer_mouvement


@transaction.atomic
def allouer_lots_fefo(medicament, quantite, date_reference=None):
    """Retourne [(lot, quantite), ...] en priorisant les lots les plus proches."""
    if quantite <= 0:
        raise ValidationError('La quantite doit etre positive.')
    date_reference = date_reference or timezone.localdate()
    lots = list(
        LotStock.objects.select_for_update()
        .filter(
            medicament=medicament,
            quantite__gt=0,
            est_bloque=False,
            date_peremption__gte=date_reference,
        )
        .order_by('date_peremption', 'id')
    )
    allocations = []
    restant = quantite
    for lot in lots:
        if restant <= 0:
            break
        pris = min(lot.quantite, restant)
        allocations.append((lot, pris))
        restant -= pris
    if restant > 0:
        raise StockInsuffisantError(
            f'Stock insuffisant pour {medicament.nom} : {restant} unite(s) manquante(s).'
        )
    return allocations


@transaction.atomic
def consommer_lots(allocations, *, reference, utilisateur, motif='Vente'):
    """Decremente les lots alloues et ecrit les mouvements de sortie."""
    for lot_alloue, quantite in allocations:
        lot = LotStock.objects.select_for_update().get(pk=lot_alloue.pk)
        if not lot.est_delivrable:
            raise LotNonDelivrableError(f'Le lot {lot.numero_lot} n est plus delivrable.')
        if lot.quantite < quantite:
            raise StockInsuffisantError(f'Stock insuffisant sur le lot {lot.numero_lot}.')
        lot.quantite -= quantite
        lot.save(update_fields=['quantite', 'modifie_le'])
        enregistrer_mouvement(
            lot.medicament, lot, MouvementStock.Type.SORTIE, -quantite,
            motif=motif, reference=reference, utilisateur=utilisateur,
        )


@transaction.atomic
def reinjecter_lot(lot, quantite, *, reference, utilisateur, motif='Retour client'):
    """Remet en stock un lot eligible lors d'un retour (RG10)."""
    if quantite <= 0:
        raise ValidationError('La quantite retournee doit etre positive.')
    lot = LotStock.objects.select_for_update().get(pk=lot.pk)
    lot.quantite += quantite
    lot.save(update_fields=['quantite', 'modifie_le'])
    enregistrer_mouvement(
        lot.medicament, lot, MouvementStock.Type.RETOUR, quantite,
        motif=motif, reference=reference, utilisateur=utilisateur,
    )
    return lot
