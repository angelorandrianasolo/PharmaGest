from django.contrib import admin

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class LigneAchatInline(admin.TabularInline):
    model = LigneAchat
    extra = 1


class LigneReceptionInline(admin.TabularInline):
    model = LigneReception
    extra = 1


@admin.register(CommandeAchat)
class CommandeAchatAdmin(admin.ModelAdmin):
    list_display = ('numero', 'fournisseur', 'date_commande', 'statut', 'total')
    list_filter = ('statut', 'fournisseur')
    search_fields = ('numero', 'fournisseur__nom')
    inlines = [LigneAchatInline]


@admin.register(ReceptionAchat)
class ReceptionAchatAdmin(admin.ModelAdmin):
    list_display = ('numero', 'commande', 'date_reception', 'total')
    search_fields = ('numero', 'commande__numero')
    inlines = [LigneReceptionInline]
