from django.urls import path

from . import views

app_name = "utilisateurs"

urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="login"),
    path("inscription/", views.InscriptionView.as_view(), name="inscription"),
    path("inscription/ok/", views.InscriptionOKView.as_view(), name="inscription_ok"),
    path("profil/", views.ProfilView.as_view(), name="profil"),
    path("profil/modifier/", views.ProfilModificationView.as_view(), name="profil_modifier"),
    path("profil/photo/supprimer/", views.PhotoSuppressionView.as_view(), name="photo_supprimer"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="logout"),
    path("mot-de-passe/", views.ChangementMotDePasseView.as_view(), name="password_change"),
    path(
        "mot-de-passe/ok/",
        views.ChangementMotDePasseOKView.as_view(),
        name="password_change_done",
    ),
    path(
        "mot-de-passe/reinitialiser/",
        views.ReinitialisationMotDePasseView.as_view(),
        name="password_reset",
    ),
    path(
        "mot-de-passe/reinitialiser/envoye/",
        views.ReinitialisationMotDePasseOKView.as_view(),
        name="password_reset_done",
    ),
    path(
        "mot-de-passe/reinitialiser/<uidb64>/<token>/",
        views.ReinitialisationConfirmationView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "mot-de-passe/reinitialiser/termine/",
        views.ReinitialisationTermineeView.as_view(),
        name="password_reset_complete",
    ),
    path("", views.UtilisateurListView.as_view(), name="liste"),
    path("creer/", views.UtilisateurCreateView.as_view(), name="creer"),
    path("<int:pk>/modifier/", views.UtilisateurUpdateView.as_view(), name="modifier"),
    path("<int:pk>/actif/", views.BasculerActifView.as_view(), name="basculer_actif"),
]
