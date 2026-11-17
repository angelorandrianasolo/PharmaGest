"""Crée les groupes Django et leur attribue les permissions de chaque rôle.

Commande idempotente : `python manage.py setup_roles`.
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from core.permissions import ADMINISTRATEUR, ROLES, ROLE_PERMISSIONS


class Command(BaseCommand):
    help = "Configure les groupes et permissions des rôles PharmaGest"

    def handle(self, *args, **options):
        for code, libelle in ROLES:
            groupe, _ = Group.objects.get_or_create(name=libelle)

            if code == ADMINISTRATEUR:
                permissions = Permission.objects.all()
            else:
                codenames = ROLE_PERMISSIONS[code]
                permissions = Permission.objects.filter(codename__in=codenames)
                trouves = set(permissions.values_list("codename", flat=True))
                manquants = sorted(set(codenames) - trouves)
                if manquants:
                    self.stderr.write(
                        f"  ⚠ permissions introuvables pour {libelle} : {', '.join(manquants)}"
                    )

            groupe.permissions.set(permissions)
            self.stdout.write(
                self.style.SUCCESS(f"{libelle} : {permissions.count()} permission(s)")
            )
