"""Valeurs disponibles dans tous les templates."""

from django.conf import settings


def parametres(request):
    return {"nom_pharmacie": settings.PHARMACIE_NOM}
