"""Ecritures de stock : réceptions, corrections et contrôle d'intégrité.

Toute modification de quantité passe par ce module afin de garantir
l'atomicité, l'absence de stock négatif et la création d'un mouvement.
"""

from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import LotStock, MouvementStock


def enregistrer_mouvement(medicament, lot, type_mouvement, quantite, *, motif, reference, utilisateur):
    """Trace une variation de stock. Fonction interne aux services."""
    return MouvementStock.objects.create(
        medicament=medicament,
        lot=lot,
        type=type_mouvement,
        quantite=quantite,
        motif=motif,
        reference=reference,
        utilisateur=utilisateur,
    )


@transaction.atomic
def enregistrer_reception(medicament, numero_lot, date_peremption, quantite,
                          prix_achat, fournisseur=None, ligne_reception=None,
                          reference="", utilisateur=None):
    if quantite <= 0:
        raise ValidationError('La quantite recue doit etre positive.')

    lot = (
        LotStock.objects.select_for_update()
        .filter(
            medicament=medicament,
            numero_lot=numero_lot,
            date_peremption=date_peremption,
            ligne_reception=ligne_reception,
        )
        .first()
    )
    if lot is None:
        lot = LotStock.objects.create(
            medicament=medicament,
            numero_lot=numero_lot,
            date_peremption=date_peremption,
            quantite=quantite,
            quantite_initiale=quantite,
            prix_achat=prix_achat,
            fournisseur=fournisseur,
            ligne_reception=ligne_reception,
            reference=reference,
        )
    else:
        lot.quantite += quantite
        lot.save(update_fields=['quantite', 'modifie_le'])

    enregistrer_mouvement(
        medicament, lot, MouvementStock.Type.ENTREE, quantite,
        motif='Reception de marchandise', reference=reference, utilisateur=utilisateur,
    )
    return lot


@transaction.atomic
def corriger_quantite(lot, nouvelle_quantite, *, motif, utilisateur, reference=''):
    """Correction d'inventaire : la quantite stockee reste toujours >= 0 (RG07)."""
    if nouvelle_quantite < 0:
        raise ValidationError('La quantite ne peut pas etre negative.')
    lot = LotStock.objects.select_for_update().get(pk=lot.pk)
    ecart = nouvelle_quantite - lot.quantite
    lot.quantite = nouvelle_quantite
    lot.save(update_fields=['quantite', 'modifie_le'])
    enregistrer_mouvement(
        lot.medicament, lot, MouvementStock.Type.CORRECTION, ecart,
        motif=motif, reference=reference, utilisateur=utilisateur,
    )
    return lot


def verifier_integrite(medicament=None):
    """Compare quantite stockee et somme des mouvements (controle de coherence)."""
    lots = LotStock.objects.all()
    if medicament is not None:
        lots = lots.filter(medicament=medicament)
    incoherences = []
    for lot in lots:
        calcule = lot.mouvements.aggregate(total=models.Sum('quantite'))['total'] or 0
        if calcule != lot.quantite:
            incoherences.append((lot, lot.quantite, calcule))
    return incoherences
