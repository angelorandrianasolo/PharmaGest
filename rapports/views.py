"""Tableau de bord et vues de génération des PDF."""

from datetime import date, timedelta

from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from achats.models import CommandeAchat, ReceptionAchat
from core.mixins import AnyPermissionRequiredMixin
from medicaments.models import Medicament
from stock.models import LotStock
from ventes.models import LigneVente, Paiement, Vente

from . import generateurs

PERMISSION_RAPPORTS = 'ventes.consulter_rapports'


class TableauDeBordView(AnyPermissionRequiredMixin, TemplateView):
    template_name = 'rapports/dashboard.html'
    permission_required = (PERMISSION_RAPPORTS,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        aujourd_hui = timezone.localdate()
        debut = aujourd_hui - timedelta(days=6)

        ventes_par_jour = []
        achats_par_jour = []
        for decalage in range(7):
            jour = debut + timedelta(days=decalage)
            total_vente = Vente.objects.filter(
                date__date=jour
            ).exclude(statut=Vente.STATUT_ANNULEE).aggregate(total=Sum('total'))['total'] or 0
            total_achat = ReceptionAchat.objects.filter(
                date_reception=jour
            ).aggregate(total=Sum('lignes__quantite', filter=Q(lignes__quantite__gt=0)))['total'] or 0
            ventes_par_jour.append({
                'jour': jour.strftime('%a %d/%m'), 'valeur': float(total_vente),
                'hauteur': max(4, float(total_vente) / 1000),
            })
            achats_par_jour.append({
                'jour': jour.strftime('%a %d/%m'), 'valeur': float(total_achat),
                'hauteur': max(4, float(total_achat) * 2),
            })

        maximum_vente = max((j['valeur'] for j in ventes_par_jour), default=1) or 1
        maximum_achat = max((j['valeur'] for j in achats_par_jour), default=1) or 1
        for jour in ventes_par_jour:
            jour['hauteur'] = max(3, jour['valeur'] / maximum_vente * 100)
        for jour in achats_par_jour:
            jour['hauteur'] = max(3, jour['valeur'] / maximum_achat * 100)

        context['ventes_par_jour'] = ventes_par_jour
        context['achats_par_jour'] = achats_par_jour
        context['medicaments_actifs'] = Medicament.objects.filter(
            statut=Medicament.STATUT_ACTIF
        ).count()
        context['ventes_du_jour'] = Vente.objects.filter(
            date__date=aujourd_hui, statut=Vente.STATUT_CONFIRMEE
        ).count()
        context['ca_du_jour'] = Vente.objects.filter(
            date__date=aujourd_hui
        ).exclude(statut=Vente.STATUT_ANNULEE).aggregate(total=Sum('total'))['total'] or 0
        context['encaissements'] = Paiement.objects.filter(
            statut=Paiement.STATUT_CONFIRME, confirme_le__date=aujourd_hui
        ).aggregate(total=Sum('montant'))['total'] or 0
        context['marge'] = LigneVente.objects.exclude(
            vente__statut=Vente.STATUT_ANNULEE
        ).annotate(valeur=(F('prix_unitaire') - F('medicament__prix_achat')) * F('quantite')
                   ).aggregate(total=Sum('valeur'))['total'] or 0

        context['stocks_faibles'] = Medicament.objects.filter(
            statut=Medicament.STATUT_ACTIF
        ).annotate(
            stock_valide=Sum('lots__quantite', filter=Q(
                lots__est_bloque=False,
                lots__date_peremption__gte=aujourd_hui,
            ))
        ).filter(
            Q(stock_valide__lte=F('seuil_alerte')) | Q(stock_valide__isnull=True)
        ).select_related('categorie')
        context['peremptions_proches'] = LotStock.objects.filter(
            quantite__gt=0,
            date_peremption__gte=aujourd_hui,
            date_peremption__lte=aujourd_hui + timedelta(days=30),
        ).select_related('medicament')
        context['lots_perimes'] = LotStock.objects.filter(
            quantite__gt=0, date_peremption__lt=aujourd_hui
        ).select_related('medicament')
        context['top_produits'] = LigneVente.objects.exclude(
            vente__statut=Vente.STATUT_ANNULEE
        ).values('medicament__nom').annotate(
            total_vendu=Sum('quantite')
        ).order_by('-total_vendu')[:5]
        return context


class RecuPdfView(AnyPermissionRequiredMixin, View):
    permission_required = ('ventes.view_vente', PERMISSION_RAPPORTS)

    def get(self, request, pk):
        return generateurs.generer_recu(get_object_or_404(Vente, pk=pk))


class FacturePdfView(AnyPermissionRequiredMixin, View):
    permission_required = ('ventes.view_vente', PERMISSION_RAPPORTS)

    def get(self, request, pk):
        return generateurs.generer_facture(get_object_or_404(Vente, pk=pk))


class BonCommandePdfView(AnyPermissionRequiredMixin, View):
    permission_required = PERMISSION_RAPPORTS

    def get(self, request, pk):
        return generateurs.generer_bon_commande(
            get_object_or_404(CommandeAchat, pk=pk)
        )


class BonReceptionPdfView(AnyPermissionRequiredMixin, View):
    permission_required = PERMISSION_RAPPORTS

    def get(self, request, pk):
        return generateurs.generer_bon_reception(
            get_object_or_404(ReceptionAchat, pk=pk)
        )


class RapportStockPdfView(AnyPermissionRequiredMixin, View):
    permission_required = PERMISSION_RAPPORTS

    def get(self, request):
        return generateurs.generer_rapport_stock()


class RapportPeremptionsPdfView(AnyPermissionRequiredMixin, View):
    permission_required = PERMISSION_RAPPORTS

    def get(self, request):
        return generateurs.generer_rapport_peremptions()


class RapportPeriodePdfView(AnyPermissionRequiredMixin, View):
    """Parent des rapports ventes/achats sur une période."""

    permission_required = PERMISSION_RAPPORTS
    generateur = None

    def get(self, request):
        fin = self._date(request.GET.get('fin')) or timezone.localdate()
        debut = self._date(request.GET.get('debut')) or (fin - timedelta(days=30))
        return self.generateur(debut, fin)

    @staticmethod
    def _date(valeur):
        try:
            return date.fromisoformat(valeur) if valeur else None
        except ValueError:
            return None


class RapportVentesPdfView(RapportPeriodePdfView):
    generateur = staticmethod(generateurs.generer_rapport_ventes)


class RapportAchatsPdfView(RapportPeriodePdfView):
    generateur = staticmethod(generateurs.generer_rapport_achats)
