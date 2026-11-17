"""Fiches fournisseurs."""

from django.db import models

from core.models import TimeStampedModel


class Fournisseur(TimeStampedModel):
    nom = models.CharField("nom ou raison sociale", max_length=200)
    adresse = models.TextField("adresse", blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    identifiant_fiscal = models.CharField("identifiant fiscal", max_length=60, blank=True)
    contact_principal = models.CharField("contact principal", max_length=120, blank=True)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "fournisseur"
        verbose_name_plural = "fournisseurs"
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["telephone"]),
        ]

    def __str__(self) -> str:
        return self.nom

    @property
    def nombre_commandes(self) -> int:
        return self.commandes.count()

    @property
    def montant_commandes(self):
        total = self.commandes.aggregate(
            total=models.Sum(
                models.F("lignes__quantite") * models.F("lignes__prix_unitaire")
            )
        )["total"]
        return total or 0
