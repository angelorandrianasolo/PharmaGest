"""Vues d'authentification et d'administration des comptes."""

from django.contrib.auth.mixins import PermissionRequiredMixin
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
from django.views.generic import CreateView, ListView, UpdateView

from core.utils import journaliser

from .forms import UtilisateurCreationForm, UtilisateurModificationForm
from .models import Utilisateur


class ConnexionView(LoginView):
    template_name = "utilisateurs/login.html"
    redirect_authenticated_user = True


class DeconnexionView(LogoutView):
    next_page = reverse_lazy("utilisateurs:login")


class ChangementMotDePasseView(PasswordChangeView):
    template_name = "utilisateurs/password_change.html"
    success_url = reverse_lazy("utilisateurs:password_change_done")


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


class BasculerActifView(PermissionRequiredMixin, View):
    permission_required = "utilisateurs.change_utilisateur"
    http_method_names = ["post"]

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk)
        if utilisateur == request.user:
            return HttpResponseForbidden("Vous ne pouvez pas désactiver votre propre compte.")
        utilisateur.is_active = not utilisateur.is_active
        utilisateur.save(update_fields=["is_active"])
        journaliser(
            request.user,
            "Activation" if utilisateur.is_active else "Désactivation",
            instance=utilisateur,
            details=f"Compte de {utilisateur.username}",
            request=request,
        )
        return redirect("utilisateurs:liste")
