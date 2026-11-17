"""Formulaires de gestion des comptes."""

from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Utilisateur


class UtilisateurCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
        )

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.synchroniser_groupes()
        return user


class UtilisateurModificationForm(UserChangeForm):
    password = None  # le mot de passe se change via la page dédiée

    class Meta(UserChangeForm.Meta):
        model = Utilisateur
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
            "is_active",
            "groups",
        )
