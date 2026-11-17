"""Vues du catalogue des médicaments."""

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import F, Q, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from core.utils import journaliser

from .forms import CategorieForm, MedicamentForm
from .models import Categorie, Medicament


class MedicamentListView(ListView):
    model = Medicament
    template_name = "medicaments/medicament_list.html"
    context_object_name = "medicaments"
    paginate_by = 15

    def get_queryset(self):
        queryset = Medicament.objects.select_related("categorie")
        recherche = self.request.GET.get("q", "").strip()
        categorie = self.request.GET.get("categorie", "").strip()
        tri = self.request.GET.get("tri", "nom")

        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche) | Q(code_barres__icontains=recherche)
            )
        if categorie.isdigit():
            queryset = queryset.filter(categorie_id=int(categorie))

        if tri not in {"nom", "prix_vente", "cree_le"}:
            tri = "nom"
        return queryset.order_by(tri)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Categorie.objects.all()
        context["filtres"] = self.request.GET
        return context


class MedicamentDetailView(DetailView):
    model = Medicament
    template_name = "medicaments/medicament_detail.html"
    context_object_name = "medicament"


class MedicamentCreateView(PermissionRequiredMixin, CreateView):
    model = Medicament
    form_class = MedicamentForm
    template_name = "medicaments/medicament_form.html"
    success_url = reverse_lazy("medicaments:liste")
    permission_required = "medicaments.add_medicament"

    def form_valid(self, form):
        form.instance.cree_par = self.request.user
        return super().form_valid(form)


class MedicamentUpdateView(PermissionRequiredMixin, UpdateView):
    model = Medicament
    form_class = MedicamentForm
    template_name = "medicaments/medicament_form.html"
    success_url = reverse_lazy("medicaments:liste")
    permission_required = "medicaments.change_medicament"


class BasculerArchivageView(PermissionRequiredMixin, View):
    """Archive ou restaure un médicament : jamais de suppression destructive."""

    permission_required = "medicaments.change_medicament"
    http_method_names = ["post"]

    def post(self, request, pk):
        medicament = get_object_or_404(Medicament, pk=pk)
        nouveau = (
            Medicament.STATUT_ACTIF
            if medicament.statut == Medicament.STATUT_ARCHIVE
            else Medicament.STATUT_ARCHIVE
        )
        medicament.statut = nouveau
        medicament.save(update_fields=["statut", "modifie_le"])
        journaliser(
            request.user,
            "Archivage" if nouveau == Medicament.STATUT_ARCHIVE else "Restauration",
            instance=medicament,
            request=request,
        )
        return redirect("medicaments:detail", pk=medicament.pk)


class CategorieListView(ListView):
    model = Categorie
    template_name = "medicaments/categorie_list.html"
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        queryset = Categorie.objects.all()
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(nom__icontains=recherche)
        return queryset.order_by("nom")


class CategorieCreateView(PermissionRequiredMixin, CreateView):
    model = Categorie
    form_class = CategorieForm
    template_name = "medicaments/categorie_form.html"
    success_url = reverse_lazy("medicaments:categories")
    permission_required = "medicaments.add_categorie"


class CategorieUpdateView(PermissionRequiredMixin, UpdateView):
    model = Categorie
    form_class = CategorieForm
    template_name = "medicaments/categorie_form.html"
    success_url = reverse_lazy("medicaments:categories")
    permission_required = "medicaments.change_categorie"


class ApercuStockView(TemplateView):
    """Petit récapitulatif des alertes, intégré à l'accueil."""

    template_name = "medicaments/apercu_stock.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["alertes"] = (
            Medicament.objects.filter(statut=Medicament.STATUT_ACTIF)
            .annotate(
                stock_valide=Sum(
                    "lots__quantite",
                    filter=Q(
                        lots__est_bloque=False,
                        lots__date_peremption__gte=timezone.localdate(),
                    ),
                )
            )
            .filter(Q(stock_valide__lte=F("seuil_alerte")) | Q(stock_valide__isnull=True))
            .select_related("categorie")[:10]
        )
        return context
