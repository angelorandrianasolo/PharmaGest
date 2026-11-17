from django.contrib import admin

from .models import Categorie, Medicament


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "nombre_medicaments")
    search_fields = ("nom",)


@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "categorie",
        "dosage",
        "prix_vente",
        "seuil_alerte",
        "statut",
    )
    list_filter = ("categorie", "statut")
    search_fields = ("nom", "denomination_generique", "code_barres")
    readonly_fields = ("cree_le", "modifie_le", "cree_par")
