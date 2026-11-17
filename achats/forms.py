"""Formulaires et formsets des achats."""

from django import forms
from django.forms import inlineformset_factory

from core.forms import BootstrapFormMixin

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class CommandeAchatForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CommandeAchat
        fields = ('fournisseur', 'date_commande', 'note')


class LigneAchatForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LigneAchat
        fields = ('medicament', 'quantite', 'prix_unitaire')


LigneAchatFormSet = inlineformset_factory(
    CommandeAchat, LigneAchat, form=LigneAchatForm, extra=2, can_delete=True
)


class ReceptionAchatForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ReceptionAchat
        fields = ('note',)


class LigneReceptionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LigneReception
        fields = (
            'ligne_achat', 'medicament', 'numero_lot', 'date_peremption',
            'quantite', 'prix_unitaire',
        )


LigneReceptionFormSet = inlineformset_factory(
    ReceptionAchat, LigneReception, form=LigneReceptionForm, extra=1, can_delete=False
)
