from django.contrib import admin

from .models import LigneVente, Paiement, RetourVente, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0
    readonly_fields = ('numero_lot', 'date_peremption', 'prix_unitaire')


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ('numero', 'date', 'client', 'statut', 'mode_paiement', 'total')
    list_filter = ('statut', 'mode_paiement')
    search_fields = ('numero', 'client__nom')
    inlines = [LigneVenteInline]


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ('vente', 'mode', 'montant', 'statut', 'reference')
    list_filter = ('statut', 'mode')


@admin.register(RetourVente)
class RetourVenteAdmin(admin.ModelAdmin):
    list_display = ('vente', 'medicament', 'quantite', 'motif', 'remis_en_stock')
    list_filter = ('remis_en_stock',)
