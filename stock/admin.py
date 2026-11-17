from django.contrib import admin

from .models import LotStock, MouvementStock


@admin.register(LotStock)
class LotStockAdmin(admin.ModelAdmin):
    list_display = (
        'medicament', 'numero_lot', 'date_peremption', 'quantite', 'est_bloque'
    )
    list_filter = ('est_bloque', 'date_peremption')
    search_fields = ('numero_lot', 'medicament__nom', 'reference')


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ('date', 'type', 'medicament', 'quantite', 'reference', 'utilisateur')
    list_filter = ('type', 'date')
    search_fields = ('reference', 'medicament__nom', 'motif')
    readonly_fields = ('date',)
