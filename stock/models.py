"""Lots de médicaments et historique des mouvements."""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class LotStock(TimeStampedModel):
    """Un lot reçu, avec sa date de péremption et sa quantité disponible."""

    medicament = models.ForeignKey(
        "medicaments.Medicament",
        verbose_name="médicament",
        on_delete=models.PROTECT,
        related_name="lots",
    )
    numero_lot = models.CharField("numéro de lot", max_length=100)
    date_peremption = models.DateField("date de péremption")
    quantite = models.PositiveIntegerField("quantité disponible", default=0)
    quantite_initiale = models.PositiveIntegerField("quantité reçue")
    prix_achat = models.DecimalField(
        "prix d'achat unitaire", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    fournisseur = models.ForeignKey(
        "fournisseurs.Fournisseur",
        verbose_name="fournisseur",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lots",
    )
    est_bloque = models.BooleanField("lot bloqué", default=False)
    motif_blocage = models.TextField("motif du blocage", blank=True)
    ligne_reception = models.ForeignKey(
        "achats.LigneReception",
        verbose_name="ligne de réception",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lots",
    )
    reference = models.CharField("référence", max_length=100, blank=True, db_index=True)

    class Meta:
        verbose_name = "lot de stock"
        verbose_name_plural = "lots de stock"
        ordering = ["date_peremption", "id"]
        indexes = [
            models.Index(fields=["medicament", "date_peremption"]),
            models.Index(fields=["date_peremption"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantite__gte=0), name="quantite_lot_non_negative"
            )
        ]

    def __str__(self) -> str:
        return f"{self.medicament.nom} — lot {self.numero_lot} ({self.quantite})"

    @property
    def est_perime(self) -> bool:
        return self.date_peremption < timezone.localdate()

    @property
    def est_delivrable(self) -> bool:
        return not self.est_bloque and not self.est_perime and self.quantite > 0


class MouvementStock(models.Model):
    """Historique traçable de chaque variation de stock (RG09)."""

    class Type(models.TextChoices):
        ENTREE = "entree", "Entrée (réception)"
        SORTIE = "sortie", "Sortie (vente)"
        CORRECTION = "correction", "Correction d'inventaire"
        RETOUR = "retour", "Retour client"
        INVENTAIRE = "inventaire", "Inventaire physique"

    medicament = models.ForeignKey(
        "medicaments.Medicament",
        verbose_name="médicament",
        on_delete=models.PROTECT,
        related_name="mouvements",
    )
    lot = models.ForeignKey(
        LotStock,
        verbose_name="lot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mouvements",
    )
    type = models.CharField("type", max_length=20, choices=Type.choices)
    quantite = models.IntegerField("quantité signée")
    motif = models.CharField("motif", max_length=250, blank=True)
    reference = models.CharField("référence", max_length=100, blank=True, db_index=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mouvements_stock",
    )
    date = models.DateTimeField("date", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        ordering = ["-date"]

    def __str__(self) -> str:
        signe = "+" if self.quantite > 0 else ""
        return f"{self.get_type_display()} {signe}{self.quantite} — {self.medicament}"
