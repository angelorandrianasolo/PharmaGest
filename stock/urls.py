from django.urls import path

from . import views

app_name = 'stock'

urlpatterns = [
    path('', views.LotStockListView.as_view(), name='lots'),
    path('mouvements/', views.MouvementStockListView.as_view(), name='mouvements'),
    path('correction/', views.CorrectionStockView.as_view(), name='correction'),
    path('<int:pk>/blocage/', views.BasculerBlocageView.as_view(), name='blocage'),
]
