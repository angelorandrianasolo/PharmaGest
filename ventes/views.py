"""Vues de la caisse, des ventes, paiements et retours."""

import uuid

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from medicaments.models import Medicament
from stock.models import LotStock

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
                {
                    'medicament': d['medicament'],
                    'quantite': d['quantite'],
                    'lot': d.get('lot'),
                }
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
        return self._rendu(request, form, formset, cle, self._panier_initial(formset))

    @staticmethod
    def _panier_initial(formset):
        """Relit le panier soumis pour le restituer après une erreur de validation."""
        panier = []
        for sous_form in formset.forms:
            prefixe = sous_form.prefix
            donnees = sous_form.data
            if donnees.get(f'{prefixe}-DELETE'):
                continue
            identifiant = donnees.get(f'{prefixe}-medicament', '')
            if not str(identifiant).isdigit():
                continue
            panier.append({
                'id': int(identifiant),
                'quantite': donnees.get(f'{prefixe}-quantite', '1'),
                'lot': donnees.get(f'{prefixe}-lot', ''),
            })
        return panier

    def _rendu(self, request, form, formset, cle, panier_initial=None):
        return render(request, self.template_name, {
            'form': form,
            'formset': formset,
            'idempotency_key': cle,
            'panier_initial': panier_initial or [],
        })


class RechercheMedicamentView(PermissionRequiredMixin, View):
    """Recherche nom / code-barres (scan) et lots délivrables pour la caisse."""

    permission_required = 'ventes.add_vente'

    def get(self, request):
        identifiant = request.GET.get('id', '').strip()
        recherche = request.GET.get('q', '').strip()
        lots = (
            LotStock.objects.filter(
                quantite__gt=0,
                est_bloque=False,
                date_peremption__gte=timezone.localdate(),
            ).order_by('date_peremption', 'id')
        )
        queryset = Medicament.objects.filter(statut=Medicament.STATUT_ACTIF)
        if identifiant.isdigit():
            queryset = queryset.filter(pk=int(identifiant))
        elif len(recherche) >= 2:
            queryset = queryset.filter(
                Q(nom__icontains=recherche)
                | Q(denomination_generique__icontains=recherche)
                | Q(code_barres__icontains=recherche)
            )
        else:
            return JsonResponse({'resultats': []})

        queryset = queryset.prefetch_related(
            Prefetch('lots', queryset=lots, to_attr='lots_disponibles')
        )[:20]
        return JsonResponse({
            'resultats': [self._serialiser(medicament) for medicament in queryset],
        })

    @staticmethod
    def _serialiser(medicament):
        return {
            'id': medicament.pk,
            'nom': medicament.nom,
            'dosage': medicament.dosage,
            'presentation': medicament.forme,
            'code_barres': medicament.code_barres or '',
            'prix': str(medicament.prix_vente),
            'stock': medicament.stock_disponible,
            'lots': [
                {
                    'id': lot.pk,
                    'numero': lot.numero_lot,
                    'peremption': lot.date_peremption.isoformat(),
                    'quantite': lot.quantite,
                    'suggere': index == 0,
                }
                for index, lot in enumerate(medicament.lots_disponibles[:10])
            ],
        }


class VenteListView(PermissionRequiredMixin, ListView):
    permission_required = 'ventes.view_vente'
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


class VenteDetailView(PermissionRequiredMixin, DetailView):
    permission_required = 'ventes.view_vente'
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
