from django.urls import path

from . import views

app_name = "fournisseurs"

urlpatterns = [
    path("", views.FournisseurListView.as_view(), name="liste"),
    path("nouveau/", views.FournisseurCreateView.as_view(), name="creer"),
    path("<int:pk>/", views.FournisseurDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.FournisseurUpdateView.as_view(), name="modifier"),
    path("<int:pk>/actif/", views.BasculerActifView.as_view(), name="basculer_actif"),
]
