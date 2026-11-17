from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Profil PharmaGest", {"fields": ("role", "telephone")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Profil PharmaGest", {"fields": ("role", "telephone")}),
    )
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active", "groups")
