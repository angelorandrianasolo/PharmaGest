from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    path("", views.ClientListView.as_view(), name="liste"),
    path("nouveau/", views.ClientCreateView.as_view(), name="creer"),
    path("<int:pk>/", views.ClientDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.ClientUpdateView.as_view(), name="modifier"),
]
