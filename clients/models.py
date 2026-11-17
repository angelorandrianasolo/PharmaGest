"""Fiches clients (données personnelles limitées au strict nécessaire)."""

from django.db import models

from core.models import TimeStampedModel


class Client(TimeStampedModel):
    nom = models.CharField("nom", max_length=150, blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    adresse = models.TextField("adresse", blank=True)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "client"
        verbose_name_plural = "clients"
        ordering = ["nom", "id"]
        indexes = [models.Index(fields=["nom"]), models.Index(fields=["telephone"])]

    def __str__(self) -> str:
        return self.nom.strip() or f"Client #{self.pk}"

    @property
    def nombre_ventes(self) -> int:
        return self.ventes.count()
