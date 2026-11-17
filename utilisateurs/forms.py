"""Formulaires de connexion, d'inscription et de gestion du profil."""

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from core.forms import BootstrapFormMixin
from core.permissions import INSCRIT

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


class ConfirmationMotDePasseMixin:
    """Exige le mot de passe actuel avant toute modification sensible."""

    def __init__(self, *args, utilisateur=None, **kwargs):
        self.utilisateur = utilisateur
        super().__init__(*args, **kwargs)
        self.fields['mot_de_passe'] = forms.CharField(
            label='Mot de passe actuel (confirmation)',
            widget=forms.PasswordInput(attrs={
                'class': 'form-control',
                'autocomplete': 'current-password',
                'placeholder': 'Saisissez votre mot de passe actuel',
            }),
            help_text='Confirmation obligatoire avant enregistrement de la modification.',
        )

    def clean_mot_de_passe(self):
        mot_de_passe = self.cleaned_data['mot_de_passe']
        if self.utilisateur is None or not self.utilisateur.check_password(mot_de_passe):
            raise forms.ValidationError('Le mot de passe saisi est incorrect.')
        return mot_de_passe


class InscriptionForm(BootstrapFormMixin, UserCreationForm):
    """Inscription publique : compte limité à la lecture, à activer par un administrateur."""

    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = ("username", "first_name", "last_name", "email", "telephone")

    email = forms.EmailField(
        label='Adresse e-mail',
        widget=forms.EmailInput(attrs={'placeholder': 'nom@pharmacie.mg'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = "Identifiant de connexion"
        self.fields['first_name'].widget.attrs['placeholder'] = "Prénom"
        self.fields['last_name'].widget.attrs['placeholder'] = "Nom"
        self.fields['telephone'].widget.attrs['placeholder'] = "032 00 000 00"

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        utilisateur.role = INSCRIT
        utilisateur.is_active = settings.INSCRIPTION_ACTIVATION_AUTO
        if commit:
            utilisateur.save()
            utilisateur.synchroniser_groupes()
        return utilisateur


class ProfilForm(ConfirmationMotDePasseMixin, BootstrapFormMixin, forms.ModelForm):
    """Modification des informations personnelles, avec confirmation du mot de passe."""

    class Meta:
        model = Utilisateur
        fields = ("photo", "first_name", "last_name", "email", "telephone")


class SuppressionPhotoForm(ConfirmationMotDePasseMixin, forms.Form):
    """Confirmation requise pour supprimer la photo de profil."""


class UtilisateurCreationForm(BootstrapFormMixin, UserCreationForm):
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


class UtilisateurModificationForm(
    ConfirmationMotDePasseMixin, BootstrapFormMixin, forms.ModelForm
):
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
