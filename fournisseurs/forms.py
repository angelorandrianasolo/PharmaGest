"""Formulaire fournisseur."""

from django import forms

from core.forms import BootstrapFormMixin

from .models import Fournisseur


class FournisseurForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = (
            "nom",
            "adresse",
            "telephone",
            "email",
            "identifiant_fiscal",
            "contact_principal",
            "actif",
        )
