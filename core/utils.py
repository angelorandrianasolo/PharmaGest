"""Utilitaires métier génériques."""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.utils import timezone
from PIL import Image

from .models import JournalAudit

FORMATS_IMAGE_AUTORISES = {"JPEG", "PNG", "WEBP", "GIF"}
TAILLE_IMAGE_MAX_OCTETS = 5 * 1024 * 1024


def valider_image(image: UploadedFile) -> UploadedFile:
    """Vérifie le type réel et la taille d'une image téléversée (8.1)."""
    if image.size > TAILLE_IMAGE_MAX_OCTETS:
        raise ValidationError("L'image ne doit pas dépasser 5 Mo.")

    try:
        with Image.open(image) as pil_image:
            if pil_image.format not in FORMATS_IMAGE_AUTORISES:
                raise ValidationError(
                    "Format d'image non autorisé (JPEG, PNG, WEBP ou GIF attendu)."
                )
            pil_image.verify()
    except ValidationError:
        raise
    except Exception as exc:  # PIL peut lever plusieurs types d'erreurs
        raise ValidationError("Le fichier n'est pas une image valide.") from exc

    image.seek(0)
    return image


def generer_numero(prefixe: str, modele: type[models.Model]) -> str:
    """Génère un numéro lisible et unique : VTE-20261117-0001.

    La base reste propriétaire de l'unicité (contrainte `unique=True`) ;
    cette fonction évite simplement les collisions overtes.
    """
    now = timezone.localtime()
    entete = f"{prefixe}-{now:%Y%m%d}-"
    dernier = (
        modele.objects.filter(numero__startswith=entete)
        .order_by("-numero")
        .values_list("numero", flat=True)
        .first()
    )
    sequence = int(dernier.rsplit("-", 1)[-1]) + 1 if dernier else 1

    while True:
        numero = f"{entete}{sequence:04d}"
        if not modele.objects.filter(numero=numero).exists():
            return numero
        sequence += 1


def journaliser(
    utilisateur,
    action: str,
    *,
    instance=None,
    modele: str = "",
    objet_id: str = "",
    details: str = "",
    request=None,
) -> JournalAudit:
    """Écrit une entrée dans le journal d'audit (RG09)."""
    if instance is not None:
        modele = instance._meta.verbose_name
        objet_id = str(instance.pk)
    ip = None
    if request is not None:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        ip = ip or request.META.get("REMOTE_ADDR")

    return JournalAudit.objects.create(
        utilisateur=utilisateur if getattr(utilisateur, "is_authenticated", False) else None,
        action=action,
        modele=modele,
        objet_id=objet_id,
        details=details,
        adresse_ip=ip,
    )
