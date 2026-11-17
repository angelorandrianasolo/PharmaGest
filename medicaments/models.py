"""Médicaments et catégories."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum

from core.models import TimeStampedModel
from core.utils import valider_image


class Categorie(TimeStampedModel):
    nom = models.CharField("nom", max_length=100, unique=True)
    description = models.TextField("description", blank=True)

    class Meta:
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.nom

    @property
    def nombre_medicaments(self) -> int:
        return self.medicaments.count()


class Medicament(TimeStampedModel):
    STATUT_ACTIF = "actif"
    STATUT_ARCHIVE = "archive"
    STATUTS = [
        (STATUT_ACTIF, "Actif"),
        (STATUT_ARCHIVE, "Archivé"),
    ]

    nom = models.CharField("nom commercial", max_length=200)
    denomination_generique = models.CharField(
        "dénomination générique", max_length=200, blank=True
    )
    categorie = models.ForeignKey(
        Categorie,
        verbose_name="catégorie",
        on_delete=models.PROTECT,
        related_name="medicaments",
    )
    forme = models.CharField("forme pharmaceutique", max_length=80, blank=True)
    dosage = models.CharField("dosage", max_length=80, blank=True)
    laboratoire = models.CharField("laboratoire", max_length=120, blank=True)
    code_barres = models.CharField("code-barres", max_length=64, blank=True, null=True)
    photo = models.ImageField(
        "photo", upload_to="medicaments/%Y/%m/", blank=True, validators=[valider_image]
    )
    prix_achat = models.DecimalField(
        "prix d'achat",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    prix_vente = models.DecimalField(
        "prix de vente",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    seuil_alerte = models.PositiveIntegerField("seuil d'alerte", default=10)
    statut = models.CharField(
        "statut", max_length=10, choices=STATUTS, default=STATUT_ACTIF
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="créé par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="medicaments_crees",
    )

    class Meta:
        verbose_name = "médicament"
        verbose_name_plural = "médicaments"
        ordering = ["nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["code_barres"],
                condition=Q(code_barres__isnull=False) & ~Q(code_barres=""),
                name="unicite_code_barres",
            ),
            models.CheckConstraint(
                condition=Q(prix_vente__gte=0) & Q(prix_achat__gte=0),
                name="prix_positifs",
            ),
        ]
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["code_barres"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self) -> str:
        return f"{self.nom}" + (f" — {self.dosage}" if self.dosage else "")

    @property
    def stock_disponible(self) -> int:
        """Quantité délivrable : lots valides, non bloqués et non périmés."""
        from django.utils import timezone

        total = self.lots.filter(
            est_bloque=False, date_peremption__gte=timezone.localdate()
        ).aggregate(total=Sum("quantite"))["total"]
        return total or 0

    @property
    def est_en_rupture(self) -> bool:
        return self.stock_disponible <= 0

    @property
    def est_sous_le_seuil(self) -> bool:
        return self.stock_disponible <= self.seuil_alerte
