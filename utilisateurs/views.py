"""Vues d'authentification, d'inscription, de profil et d'administration des comptes."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from core.utils import journaliser

from .forms import (
    ConnexionForm,
    InscriptionForm,
    ProfilForm,
    SuppressionPhotoForm,
    UtilisateurCreationForm,
    UtilisateurModificationForm,
)
from .models import Utilisateur


class ConnexionView(LoginView):
    template_name = "utilisateurs/login.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


class DeconnexionView(LogoutView):
    next_page = reverse_lazy("utilisateurs:login")


class InscriptionView(CreateView):
    """Création d'un compte visiteur, soumis à validation administrative."""

    form_class = InscriptionForm
    template_name = "utilisateurs/inscription.html"
    success_url = reverse_lazy("utilisateurs:inscription_ok")

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(
            self.object,
            "Inscription",
            details="Compte créé via le formulaire public",
            request=self.request,
        )
        return reponse


class InscriptionOKView(TemplateView):
    template_name = "utilisateurs/inscription_ok.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activation_auto"] = settings.INSCRIPTION_ACTIVATION_AUTO
        return context


class ChangementMotDePasseView(LoginRequiredMixin, PasswordChangeView):
    template_name = "utilisateurs/password_change.html"
    success_url = reverse_lazy("utilisateurs:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, "Votre mot de passe a été modifié avec succès.")
        journaliser(self.request.user, "Mot de passe modifié", request=self.request)
        return super().form_valid(form)


class ChangementMotDePasseOKView(PasswordChangeDoneView):
    template_name = "utilisateurs/password_change_done.html"


class ReinitialisationMotDePasseView(PasswordResetView):
    template_name = "utilisateurs/password_reset.html"
    email_template_name = "utilisateurs/password_reset_email.html"
    success_url = reverse_lazy("utilisateurs:password_reset_done")


class ReinitialisationMotDePasseOKView(PasswordResetDoneView):
    template_name = "utilisateurs/password_reset_done.html"


class ReinitialisationConfirmationView(PasswordResetConfirmView):
    template_name = "utilisateurs/password_reset_confirm.html"
    success_url = reverse_lazy("utilisateurs:password_reset_complete")


class ReinitialisationTermineeView(PasswordResetCompleteView):
    template_name = "utilisateurs/password_reset_complete.html"


class ProfilView(LoginRequiredMixin, TemplateView):
    """Affiche les seules informations du compte que l'utilisateur peut modifier."""

    template_name = "utilisateurs/profil.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ProfilForm(
            instance=self.request.user, utilisateur=self.request.user
        )
        return context


class ProfilModificationView(LoginRequiredMixin, UpdateView):
    """Modification du profil, conditionnée à la confirmation du mot de passe."""

    model = Utilisateur
    form_class = ProfilForm
    template_name = "utilisateurs/profil.html"
    success_url = reverse_lazy("utilisateurs:profil")

    def get_object(self, queryset=None):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["utilisateur"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Votre profil a été mis à jour.")
        journaliser(self.request.user, "Profil modifié", request=self.request)
        return super().form_valid(form)


class PhotoSuppressionView(LoginRequiredMixin, View):
    """Suppression de la photo de profil après confirmation du mot de passe."""

    http_method_names = ["post"]

    def post(self, request):
        form = SuppressionPhotoForm(request.POST, utilisateur=request.user)
        if not form.is_valid():
            messages.error(request, "Mot de passe incorrect : photo non supprimée.")
            return redirect("utilisateurs:profil")
        if request.user.photo:
            request.user.photo.delete(save=False)
            request.user.photo = None
            request.user.save(update_fields=["photo"])
            journaliser(request.user, "Photo de profil supprimée", request=request)
            messages.success(request, "La photo de profil a été supprimée.")
        else:
            messages.info(request, "Aucune photo de profil à supprimer.")
        return redirect("utilisateurs:profil")


class UtilisateurListView(PermissionRequiredMixin, ListView):
    model = Utilisateur
    template_name = "utilisateurs/utilisateur_list.html"
    context_object_name = "utilisateurs"
    paginate_by = 20
    permission_required = "utilisateurs.view_utilisateur"


class UtilisateurCreateView(PermissionRequiredMixin, CreateView):
    model = Utilisateur
    form_class = UtilisateurCreationForm
    template_name = "utilisateurs/utilisateur_form.html"
    success_url = reverse_lazy("utilisateurs:liste")
    permission_required = "utilisateurs.add_utilisateur"


class UtilisateurUpdateView(PermissionRequiredMixin, UpdateView):
    model = Utilisateur
    form_class = UtilisateurModificationForm
    template_name = "utilisateurs/utilisateur_form.html"
    success_url = reverse_lazy("utilisateurs:liste")
    permission_required = "utilisateurs.change_utilisateur"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["utilisateur"] = self.request.user
        return kwargs

    def form_valid(self, form):
        reponse = super().form_valid(form)
        self.object.synchroniser_groupes()
        journaliser(
            self.request.user, "Compte modifié", instance=self.object,
            request=self.request,
        )
        return reponse


class BasculerActifView(PermissionRequiredMixin, View):
    permission_required = "utilisateurs.change_utilisateur"
    http_method_names = ["post"]

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk)
        if utilisateur == request.user:
            return HttpResponseForbidden("Vous ne pouvez pas désactiver votre propre compte.")
        utilisateur.is_active = not utilisateur.is_active
        utilisateur.save(update_fields=["is_active"])
        if utilisateur.is_active:
            utilisateur.synchroniser_groupes()
        journaliser(
            request.user,
            "Activation" if utilisateur.is_active else "Désactivation",
            instance=utilisateur,
            details=f"Compte de {utilisateur.username}",
            request=request,
        )
        return redirect("utilisateurs:liste")
