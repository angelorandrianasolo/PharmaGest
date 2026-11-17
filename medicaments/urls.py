from django.urls import path

from . import views

app_name = "medicaments"

urlpatterns = [
    path("", views.MedicamentListView.as_view(), name="liste"),
    path("nouveau/", views.MedicamentCreateView.as_view(), name="creer"),
    path("<int:pk>/", views.MedicamentDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.MedicamentUpdateView.as_view(), name="modifier"),
    path("<int:pk>/archiver/", views.BasculerArchivageView.as_view(), name="archiver"),
    path("categories/", views.CategorieListView.as_view(), name="categories"),
    path("categories/nouvelle/", views.CategorieCreateView.as_view(), name="categorie_creer"),
    path(
        "categories/<int:pk>/modifier/",
        views.CategorieUpdateView.as_view(),
        name="categorie_modifier",
    ),
]
