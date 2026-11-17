from django.urls import path

from . import views

app_name = 'rapports'

urlpatterns = [
    path('', views.TableauDeBordView.as_view(), name='dashboard'),
    path('vente/<int:pk>/recu.pdf', views.RecuPdfView.as_view(), name='recu'),
    path('vente/<int:pk>/facture.pdf', views.FacturePdfView.as_view(), name='facture'),
    path('commande/<int:pk>/bon.pdf', views.BonCommandePdfView.as_view(), name='bon_commande'),
    path('reception/<int:pk>/bon.pdf', views.BonReceptionPdfView.as_view(), name='bon_reception'),
    path('stock.pdf', views.RapportStockPdfView.as_view(), name='rapport_stock'),
    path('peremptions.pdf', views.RapportPeremptionsPdfView.as_view(), name='rapport_peremptions'),
    path('ventes.pdf', views.RapportVentesPdfView.as_view(), name='rapport_ventes'),
    path('achats.pdf', views.RapportAchatsPdfView.as_view(), name='rapport_achats'),
]
