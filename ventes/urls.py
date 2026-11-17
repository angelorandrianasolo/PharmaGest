from django.urls import path

from . import views

app_name = 'ventes'

urlpatterns = [
    path('', views.VenteListView.as_view(), name='liste'),
    path('caisse/', views.CaisseView.as_view(), name='caisse'),
    path('<int:pk>/', views.VenteDetailView.as_view(), name='detail'),
    path('<int:pk>/paiement/confirmer/', views.ConfirmerPaiementView.as_view(), name='paiement_confirmer'),
    path('<int:pk>/retour/', views.CreerRetourView.as_view(), name='retour'),
    path('<int:pk>/annuler/', views.AnnulerVenteView.as_view(), name='annuler'),
]
