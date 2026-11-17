from django.contrib import admin

from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "email", "actif")
    list_filter = ("actif",)
    search_fields = ("nom", "telephone", "email", "identifiant_fiscal")
