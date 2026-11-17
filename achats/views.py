"""Vues des commandes et réceptions."""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import CommandeAchatForm, LigneAchatFormSet, LigneReceptionFormSet, ReceptionAchatForm
from .models import CommandeAchat, LigneReception
from .services import annuler_commande, creer_commande, receptionner_commande, valider_commande


class CommandeListView(ListView):
    model = CommandeAchat
    template_name = 'achats/commande_list.html'
    context_object_name = 'commandes'
    paginate_by = 20


class CommandeDetailView(DetailView):
    model = CommandeAchat
    template_name = 'achats/commande_detail.html'
    context_object_name = 'commande'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['receptions'] = self.object.receptions.prefetch_related('lignes')
        return context


class CommandeCreateView(PermissionRequiredMixin, View):
    template_name = 'achats/commande_form.html'
    permission_required = 'achats.add_commandeachat'

    def get(self, request):
        return render(request, self.template_name, {
            'form': CommandeAchatForm(), 'formset': LigneAchatFormSet(),
        })

    def post(self, request):
        form = CommandeAchatForm(request.POST)
        formset = LigneAchatFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            lignes = []
            for donnees in formset.cleaned_data:
                if not donnees or donnees.get('DELETE'):
                    continue
                lignes.append({
                    'medicament': donnees['medicament'],
                    'quantite': donnees['quantite'],
                    'prix_unitaire': donnees['prix_unitaire'],
                })
            try:
                commande = creer_commande(
                    form.cleaned_data['fournisseur'], request.user, lignes,
                    note=form.cleaned_data.get('note', ''),
                )
                messages.success(request, 'Commande créée en brouillon.')
                return redirect('achats:commande_detail', pk=commande.pk)
            except Exception as exc:
                messages.error(request, str(exc))
        return render(request, self.template_name, {'form': form, 'formset': formset})


class ReceptionCreateView(PermissionRequiredMixin, View):
    template_name = 'achats/reception_form.html'
    permission_required = 'achats.receptionner_commande'

    def get(self, request, pk):
        commande = get_object_or_404(CommandeAchat, pk=pk)
        formset = LigneReceptionFormSet(queryset=LigneReception.objects.none())
        for sous_form in formset.forms:
            sous_form.fields['ligne_achat'].queryset = commande.lignes.all()
        return render(request, self.template_name, {
            'commande': commande, 'form': ReceptionAchatForm(), 'formset': formset,
        })

    def post(self, request, pk):
        commande = get_object_or_404(CommandeAchat, pk=pk)
        form = ReceptionAchatForm(request.POST)
        formset = LigneReceptionFormSet(
            request.POST, queryset=LigneReception.objects.none()
        )
        for sous_form in formset.forms:
            sous_form.fields['ligne_achat'].queryset = commande.lignes.all()
        if form.is_valid() and formset.is_valid():
            lignes = []
            for donnees in formset.cleaned_data:
                if not donnees:
                    continue
                lignes.append(donnees)
            try:
                receptionner_commande(
                    commande, lignes, request.user, note=form.cleaned_data.get('note', '')
                )
                messages.success(request, 'Réception validée : le stock a été mis à jour.')
                return redirect('achats:commande_detail', pk=commande.pk)
            except Exception as exc:
                messages.error(request, str(exc))
        return render(request, self.template_name, {
            'commande': commande, 'form': form, 'formset': formset,
        })


class ValiderCommandeView(PermissionRequiredMixin, View):
    permission_required = 'achats.valider_commande'
    http_method_names = ['post']

    def post(self, request, pk):
        commande = get_object_or_404(CommandeAchat, pk=pk)
        try:
            valider_commande(commande, request.user)
            messages.success(request, 'Commande validée.')
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect('achats:commande_detail', pk=commande.pk)


class AnnulerCommandeView(PermissionRequiredMixin, View):
    permission_required = 'achats.annuler_commande'
    http_method_names = ['post']

    def post(self, request, pk):
        commande = get_object_or_404(CommandeAchat, pk=pk)
        try:
            annuler_commande(commande, request.user)
            messages.success(request, 'Commande annulée.')
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect('achats:commande_detail', pk=commande.pk)
