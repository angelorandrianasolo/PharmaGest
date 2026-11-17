"""Compte utilisateur et rôles."""

from django.contrib.auth.models import AbstractUser, Group
from django.db import models

from core.permissions import PHARMACIEN, ROLES


class Utilisateur(AbstractUser):
    """Utilisateur de l'application : un compte peut cumuler plusieurs groupes."""

    role = models.CharField(
        "rôle principal", max_length=32, choices=ROLES, default=PHARMACIEN
    )
    telephone = models.CharField("téléphone", max_length=30, blank=True)

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["username"]

    def __str__(self) -> str:
        nom = self.get_full_name().strip() or self.username
        return f"{nom} — {self.get_role_display()}"

    def synchroniser_groupes(self) -> None:
        """Aligne les groupes Django sur le rôle principal choisi."""
        groupe = Group.objects.filter(name=self.get_role_display()).first()
        if groupe is not None:
            self.groups.set([groupe])
