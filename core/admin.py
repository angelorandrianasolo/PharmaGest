from django.contrib import admin

from .models import JournalAudit


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ("date", "utilisateur", "action", "modele", "objet_id")
    list_filter = ("action", "modele", "date")
    search_fields = ("action", "details", "objet_id", "utilisateur__username")
    readonly_fields = ("date", "utilisateur", "action", "modele", "objet_id", "details")

    def has_add_permission(self, request):
        return False
