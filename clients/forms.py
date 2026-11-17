"""Formulaire client."""

from django import forms

from core.forms import BootstrapFormMixin

from .models import Client


class ClientForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = ("nom", "telephone", "email", "adresse", "actif")
