"""Modèles partagés par toutes les applications."""

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Horodatage automatique de la création et de la dernière modification."""

    cree_le = models.DateTimeField("créé le", auto_now_add=True, db_index=True)
    modifie_le = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        abstract = True


class JournalAudit(models.Model):
    """Trace des opérations sensibles (RG09)."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actions",
    )
    action = models.CharField("action", max_length=120)
    modele = models.CharField("modèle", max_length=100, blank=True)
    objet_id = models.CharField("identifiant de l'objet", max_length=100, blank=True)
    details = models.TextField("détails", blank=True)
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    date = models.DateTimeField("date", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ["-date"]
        indexes = [models.Index(fields=["modele", "objet_id"])]

    def __str__(self) -> str:
        who = self.utilisateur or "Système"
        return f"{self.date:%d/%m/%Y %H:%M} — {who} — {self.action}"
