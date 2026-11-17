"""Formulaires de la caisse, des paiements et des retours."""

from django import forms
from django.forms import formset_factory
from django.utils import timezone

from core.forms import BootstrapFormMixin
from medicaments.models import Medicament
from stock.models import LotStock

from .models import Vente


class VenteForm(BootstrapFormMixin, forms.Form):
    client = forms.ModelChoiceField(
        queryset=None, label='Client (facultatif)', required=False
    )
    mode_paiement = forms.ChoiceField(label='Mode de paiement', choices=Vente.MODES)
    note = forms.CharField(label='Note', required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from clients.models import Client

        self.fields['client'].queryset = Client.objects.filter(actif=True)


class LigneVenteForm(BootstrapFormMixin, forms.Form):
    medicament = forms.ModelChoiceField(
        label='Médicament',
        queryset=Medicament.objects.filter(statut=Medicament.STATUT_ACTIF),
    )
    quantite = forms.IntegerField(label='Quantité', min_value=1, initial=1)
    lot = forms.ModelChoiceField(
        label='Lot (facultatif)',
        queryset=LotStock.objects.none(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            medicament_id = self.data.get(self.add_prefix('medicament'), '')
            if str(medicament_id).isdigit():
                self.fields['lot'].queryset = LotStock.objects.filter(
                    medicament_id=int(medicament_id),
                    quantite__gt=0,
                    est_bloque=False,
                    date_peremption__gte=timezone.localdate(),
                ).order_by('date_peremption', 'id')


LigneVenteFormSet = formset_factory(LigneVenteForm, extra=1, can_delete=True)


class ConfirmationPaiementForm(BootstrapFormMixin, forms.Form):
    reference = forms.CharField(label='Référence de la transaction', max_length=120)


class RetourForm(BootstrapFormMixin, forms.Form):
    quantite = forms.IntegerField(label='Quantité retournée', min_value=1)
    motif = forms.CharField(label='Motif', max_length=250)
    remettre_en_stock = forms.BooleanField(
        label='Réintégrer en stock si éligible', required=False, initial=True
    )
