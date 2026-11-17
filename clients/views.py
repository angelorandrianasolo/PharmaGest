"""Vues de gestion des clients."""

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import ClientForm
from .models import Client


class ClientListView(ListView):
    model = Client
    template_name = "clients/client_list.html"
    context_object_name = "clients"
    paginate_by = 20

    def get_queryset(self):
        queryset = Client.objects.all()
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche) | Q(telephone__icontains=recherche)
            )
        return queryset.order_by("nom", "id")


class ClientDetailView(DetailView):
    model = Client
    template_name = "clients/client_detail.html"
    context_object_name = "client"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ventes"] = self.object.ventes.select_related("utilisateur").order_by(
            "-date"
        )[:20]
        return context


class ClientCreateView(PermissionRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "clients/client_form.html"
    success_url = reverse_lazy("clients:liste")
    permission_required = "clients.add_client"


class ClientUpdateView(PermissionRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "clients/client_form.html"
    success_url = reverse_lazy("clients:liste")
    permission_required = "clients.change_client"
