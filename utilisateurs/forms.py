"""Formulaires de gestion des comptes."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import Utilisateur


class ConnexionForm(AuthenticationForm):
    """Formulaire de connexion avec indications et autocomplétion navigateur."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Votre identifiant',
            'autocomplete': 'username',
            'autofocus': True,
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': 'Votre mot de passe',
            'autocomplete': 'current-password',
        })
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


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
