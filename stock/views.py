"""Vues de consultation et de correction des stocks."""

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView

from core.mixins import AnyPermissionRequiredMixin
from core.utils import journaliser

from .forms import CorrectionStockForm
from .models import LotStock, MouvementStock
from .services import corriger_quantite


class LotStockListView(AnyPermissionRequiredMixin, ListView):
    permission_required = ('stock.view_lotstock', 'stock.view_mouvementstock')
    model = LotStock
    template_name = 'stock/lotstock_list.html'
    context_object_name = 'lots'
    paginate_by = 20

    def get_queryset(self):
        queryset = LotStock.objects.select_related('medicament', 'fournisseur')
        recherche = self.request.GET.get('q', '').strip()
        if recherche:
            queryset = queryset.filter(
                Q(medicament__nom__icontains=recherche)
                | Q(numero_lot__icontains=recherche)
            )
        if self.request.GET.get('perimes') == '1':
            from django.utils import timezone

            queryset = queryset.filter(date_peremption__lt=timezone.localdate())
        return queryset.order_by('date_peremption', 'id')


class MouvementStockListView(AnyPermissionRequiredMixin, ListView):
    permission_required = ('stock.view_lotstock', 'stock.view_mouvementstock')
    model = MouvementStock
    template_name = 'stock/mouvementstock_list.html'
    context_object_name = 'mouvements'
    paginate_by = 25

    def get_queryset(self):
        return MouvementStock.objects.select_related(
            'medicament', 'lot', 'utilisateur'
        ).order_by('-date')


class CorrectionStockView(PermissionRequiredMixin, FormView):
    template_name = 'stock/correction_form.html'
    form_class = CorrectionStockForm
    success_url = reverse_lazy('stock:lots')
    permission_required = 'stock.change_lotstock'

    def form_valid(self, form):
        lot = form.cleaned_data['lot']
        nouvelle = form.cleaned_data['nouvelle_quantite']
        motif = form.cleaned_data['motif']
        corriger_quantite(
            lot, nouvelle, motif=motif, utilisateur=self.request.user,
            reference='INV',
        )
        journaliser(
            self.request.user, 'Correction de stock', instance=lot,
            details=f'{lot.quantite} -> {nouvelle} : {motif}', request=self.request,
        )
        messages.success(self.request, 'Stock corrigé et mouvement enregistré.')
        return super().form_valid(form)


class BasculerBlocageView(PermissionRequiredMixin, View):
    permission_required = 'stock.change_lotstock'
    http_method_names = ['post']

    def post(self, request, pk):
        lot = LotStock.objects.get(pk=pk)
        lot.est_bloque = not lot.est_bloque
        lot.save(update_fields=['est_bloque', 'modifie_le'])
        journaliser(
            request.user, 'Lot bloqué' if lot.est_bloque else 'Lot débloqué',
            instance=lot, request=request,
        )
        return redirect('stock:lots')
