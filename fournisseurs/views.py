"""Vues de gestion des fournisseurs."""

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.utils import journaliser

from .forms import FournisseurForm
from .models import Fournisseur


class FournisseurListView(ListView):
    model = Fournisseur
    template_name = "fournisseurs/fournisseur_list.html"
    context_object_name = "fournisseurs"
    paginate_by = 20

    def get_queryset(self):
        queryset = Fournisseur.objects.all()
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche) | Q(telephone__icontains=recherche)
            )
        return queryset.order_by("nom")


class FournisseurDetailView(DetailView):
    model = Fournisseur
    template_name = "fournisseurs/fournisseur_detail.html"
    context_object_name = "fournisseur"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["commandes"] = self.object.commandes.select_related("fournisseur").order_by(
            "-date_commande"
        )[:20]
        return context


class FournisseurCreateView(PermissionRequiredMixin, CreateView):
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "fournisseurs/fournisseur_form.html"
    success_url = reverse_lazy("fournisseurs:liste")
    permission_required = "fournisseurs.add_fournisseur"


class FournisseurUpdateView(PermissionRequiredMixin, UpdateView):
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "fournisseurs/fournisseur_form.html"
    success_url = reverse_lazy("fournisseurs:liste")
    permission_required = "fournisseurs.change_fournisseur"


class BasculerActifView(PermissionRequiredMixin, View):
    """Désactive un fournisseur sans effacer ses opérations passées."""

    permission_required = "fournisseurs.change_fournisseur"
    http_method_names = ["post"]

    def post(self, request, pk):
        fournisseur = get_object_or_404(Fournisseur, pk=pk)
        fournisseur.actif = not fournisseur.actif
        fournisseur.save(update_fields=["actif", "modifie_le"])
        journaliser(
            request.user,
            "Fournisseur activé" if fournisseur.actif else "Fournisseur désactivé",
            instance=fournisseur,
            request=request,
        )
        return redirect("fournisseurs:liste")
