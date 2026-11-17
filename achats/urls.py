from django.urls import path

from . import views

app_name = 'achats'

urlpatterns = [
    path('', views.CommandeListView.as_view(), name='liste'),
    path('nouvelle/', views.CommandeCreateView.as_view(), name='commande_creer'),
    path('<int:pk>/', views.CommandeDetailView.as_view(), name='commande_detail'),
    path('<int:pk>/valider/', views.ValiderCommandeView.as_view(), name='commande_valider'),
    path('<int:pk>/annuler/', views.AnnulerCommandeView.as_view(), name='commande_annuler'),
    path('<int:pk>/receptionner/', views.ReceptionCreateView.as_view(), name='reception_creer'),
]
