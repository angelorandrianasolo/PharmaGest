"""Formulaires de gestion des stocks."""

from django import forms

from core.forms import BootstrapFormMixin

from .models import LotStock


class CorrectionStockForm(BootstrapFormMixin, forms.Form):
    lot = forms.ModelChoiceField(
        queryset=LotStock.objects.select_related('medicament').all(),
        label='Lot',
    )
    nouvelle_quantite = forms.IntegerField(label='Nouvelle quantité', min_value=0)
    motif = forms.CharField(label='Motif', max_length=250)
