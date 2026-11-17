"""Vues de la caisse, des ventes, paiements et retours."""

import uuid

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from .forms import ConfirmationPaiementForm, LigneVenteFormSet, RetourForm, VenteForm
from .models import LigneVente, Paiement, Vente
from .services import annuler_vente, confirmer_paiement, creer_retour, creer_vente


class CaisseView(PermissionRequiredMixin, View):
    template_name = 'ventes/caisse.html'
    permission_required = 'ventes.add_vente'

    def get(self, request):
        return self._rendu(request, VenteForm(), LigneVenteFormSet(), str(uuid.uuid4()))

    def post(self, request):
        form = VenteForm(request.POST)
        formset = LigneVenteFormSet(request.POST)
        cle = request.POST.get('idempotency_key') or str(uuid.uuid4())
        if form.is_valid() and formset.is_valid():
            lignes = [
                {'medicament': d['medicament'], 'quantite': d['quantite']}
                for d in formset.cleaned_data
                if d and not d.get('DELETE')
            ]
            try:
                vente = creer_vente(
                    lignes, request.user,
                    client=form.cleaned_data['client'],
                    mode_paiement=form.cleaned_data['mode_paiement'],
                    idempotency_key=cle,
                    note=form.cleaned_data.get('note', ''),
                )
                messages.success(request, f'Vente {vente.numero} enregistrée.')
                return redirect('ventes:detail', pk=vente.pk)
            except Exception as exc:
                messages.error(request, str(exc))
        return self._rendu(request, form, formset, cle)

    def _rendu(self, request, form, formset, cle):
        return render(request, self.template_name, {
            'form': form, 'formset': formset, 'idempotency_key': cle,
        })


class VenteListView(ListView):
    model = Vente
    template_name = 'ventes/vente_list.html'
    context_object_name = 'ventes'
    paginate_by = 20

    def get_queryset(self):
        queryset = Vente.objects.select_related('client', 'utilisateur')
        recherche = self.request.GET.get('q', '').strip()
        if recherche:
            queryset = queryset.filter(
                Q(numero__icontains=recherche) | Q(client__nom__icontains=recherche)
            )
        return queryset.order_by('-date')


class VenteDetailView(DetailView):
    model = Vente
    template_name = 'ventes/vente_detail.html'
    context_object_name = 'vente'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['paiements'] = self.object.paiements.all()
        context['retours'] = self.object.retours.select_related('medicament')
        return context


class ConfirmerPaiementView(PermissionRequiredMixin, FormView):
    template_name = 'ventes/paiement_confirmation.html'
    form_class = ConfirmationPaiementForm
    permission_required = 'ventes.confirmer_paiement'

    def dispatch(self, request, *args, **kwargs):
        self.paiement = get_object_or_404(Paiement, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['paiement'] = self.paiement
        return context

    def form_valid(self, form):
        confirmer_paiement(
            self.paiement, form.cleaned_data['reference'], self.request.user
        )
        messages.success(self.request, 'Paiement confirmé.')
        return redirect('ventes:detail', pk=self.paiement.vente_id)


class CreerRetourView(PermissionRequiredMixin, FormView):
    template_name = 'ventes/retour_form.html'
    form_class = RetourForm
    permission_required = 'ventes.valider_retour'

    def dispatch(self, request, *args, **kwargs):
        self.ligne = get_object_or_404(LigneVente, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ligne'] = self.ligne
        return context

    def form_valid(self, form):
        try:
            creer_retour(
                self.ligne,
                form.cleaned_data['quantite'],
                form.cleaned_data['motif'],
                self.request.user,
                remettre_en_stock=form.cleaned_data['remettre_en_stock'],
            )
            messages.success(self.request, 'Retour enregistré et tracé.')
        except Exception as exc:
            messages.error(self.request, str(exc))
            return self.render_to_response(self.get_context_data(form=form))
        return redirect('ventes:detail', pk=self.ligne.vente_id)


class AnnulerVenteView(PermissionRequiredMixin, View):
    permission_required = 'ventes.annuler_vente'
    http_method_names = ['post']

    def post(self, request, pk):
        vente = get_object_or_404(Vente, pk=pk)
        try:
            annuler_vente(vente, 'Annulation demandée', request.user)
            messages.success(request, 'Vente annulée par opérations compensatoires.')
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect('ventes:detail', pk=vente.pk)
