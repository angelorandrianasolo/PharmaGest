"""Formulaires des médicaments et catégories."""

from django import forms

from core.forms import BootstrapFormMixin

from .models import Categorie, Medicament


class CategorieForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ("nom", "description")


class MedicamentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Medicament
        fields = (
            "nom",
            "denomination_generique",
            "categorie",
            "forme",
            "dosage",
            "laboratoire",
            "code_barres",
            "photo",
            "prix_achat",
            "prix_vente",
            "seuil_alerte",
            "statut",
        )

    def clean_code_barres(self):
        code = (self.cleaned_data.get("code_barres") or "").strip()
        return code or None
