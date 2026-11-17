"""Pages communes (accueil et healthcheck)."""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from achats.models import ReceptionAchat
from medicaments.models import Medicament
from stock.models import LotStock
from ventes.models import Paiement, Vente


@login_required
def home(request):
    """Accueil : indicateurs et activité réels, filtrés selon les permissions."""
    aujourd_hui = timezone.localdate()
    debut_jour = timezone.localtime().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    context = {
        "alertes": (
            Medicament.objects.filter(statut=Medicament.STATUT_ACTIF)
            .annotate(
                stock_valide=Sum(
                    "lots__quantite",
                    filter=Q(
                        lots__est_bloque=False,
                        lots__date_peremption__gte=aujourd_hui,
                    ),
                )
            )
            .filter(
                Q(stock_valide__lte=F("seuil_alerte")) | Q(stock_valide__isnull=True)
            )
            .select_related("categorie")[:5]
        ),
    }

    if request.user.has_perm("ventes.view_vente") or request.user.has_perm(
        "ventes.consulter_rapports"
    ):
        ventes_jour = Vente.objects.filter(date__gte=debut_jour)
        context["stats_du_jour"] = {
            "ventes": ventes_jour.filter(statut=Vente.STATUT_CONFIRMEE).count(),
            "chiffre_affaires": ventes_jour.filter(
                statut=Vente.STATUT_CONFIRMEE
            ).aggregate(total=Sum("total"))["total"]
            or 0,
            "en_attente": ventes_jour.filter(
                statut=Vente.STATUT_EN_ATTENTE
            ).count(),
        }
        context["ventes_recentes"] = (
            Vente.objects.select_related("client").order_by("-date")[:5]
        )

    if request.user.has_perm("stock.view_lotstock") or request.user.has_perm(
        "stock.view_mouvementstock"
    ):
        context["lots_a_surveiller"] = (
            LotStock.objects.select_related("medicament")
            .filter(
                quantite__gt=0,
                date_peremption__lte=aujourd_hui + timedelta(days=30),
            )
            .order_by("date_peremption")[:5]
        )

    if request.user.has_perm("achats.view_commandeachat"):
        context["receptions_du_jour"] = ReceptionAchat.objects.filter(
            date_reception=aujourd_hui
        ).count()

    if request.user.has_perm("ventes.confirmer_paiement"):
        context["paiements_en_attente"] = (
            Paiement.objects.filter(statut=Paiement.STATUT_EN_ATTENTE)
            .select_related("vente")
            .order_by("cree_le")[:5]
        )

    return render(request, "home.html", context)


def health(request):
    """Endpoint simple utilisable par un monitoring ou un healthcheck Docker."""
    return JsonResponse({"statut": "ok", "application": "PharmaGest"})
