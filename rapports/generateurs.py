"""Documents métier produits par le module rapports."""

from django.utils import timezone

from achats.models import ReceptionAchat
from medicaments.models import Medicament
from stock.models import LotStock
from ventes.models import Vente

from .documents import DocumentPdf


def _date(valeur):
    return valeur.strftime('%d/%m/%Y') if valeur else '-'


def _lignes_vente(vente):
    return [
        [l.medicament.nom, l.numero_lot, str(l.quantite),
         f'{l.prix_unitaire} Ar', f'{l.sous_total} Ar']
        for l in vente.lignes.select_related('medicament')
    ]


def _entete_document(doc, titre, numero, date):
    doc.paragraphe(f'<b>Numéro :</b> {numero} &nbsp;&nbsp; <b>Date :</b> {_date(date)}')


def generer_recu(vente):
    doc = DocumentPdf('Reçu de vente', f'Vente {vente.numero}')
    _entete_document(doc, 'Reçu', vente.numero, vente.date)
    doc.paragraphe(f'<b>Client :</b> {vente.client or "Client comptoir"}')
    doc.paragraphe(f'<b>Caissier :</b> {vente.utilisateur or "-"}')
    doc.tableau(
        [['Médicament', 'Lot', 'Qté', 'P.U.', 'Sous-total']] + _lignes_vente(vente),
        largeurs=[170, 70, 35, 65, 75],
    )
    doc.paragraphe(f'<b>TOTAL :</b> {vente.total} Ar')
    doc.paragraphe(f'Mode de paiement : {vente.get_mode_paiement_display()}')
    return doc.reponse(f'recu-{vente.numero}')


def generer_facture(vente):
    doc = DocumentPdf('Facture de vente', f'Facture {vente.numero}')
    _entete_document(doc, 'Facture', vente.numero, vente.date)
    doc.paragraphe(f'<b>Client :</b> {vente.client or "Client comptoir"}')
    doc.tableau(
        [['Désignation', 'Lot', 'Qté', 'P.U.', 'Montant']] + _lignes_vente(vente),
        largeurs=[170, 70, 35, 65, 75],
    )
    doc.paragraphe(f'<b>Total TTC :</b> {vente.total} Ar')
    doc.paragraphe(
        'Document généré par PharmaGest. Mentions légales et fiscales à adapter '
        'selon la réglementation applicable.'
    )
    return doc.reponse(f'facture-{vente.numero}')


def generer_bon_commande(commande):
    doc = DocumentPdf('Bon de commande', commande.numero)
    _entete_document(doc, 'Commande', commande.numero, commande.date_commande)
    doc.paragraphe(f'<b>Fournisseur :</b> {commande.fournisseur}')
    lignes = [
        [l.medicament.nom, str(l.quantite), f'{l.prix_unitaire} Ar', f'{l.sous_total} Ar']
        for l in commande.lignes.select_related('medicament')
    ]
    doc.tableau([['Médicament', 'Qté', 'P.U.', 'Sous-total']] + lignes)
    doc.paragraphe(f'<b>Total :</b> {commande.total} Ar')
    doc.paragraphe(f'<b>Statut :</b> {commande.get_statut_display()}')
    return doc.reponse(f'bon-commande-{commande.numero}')


def generer_bon_reception(reception):
    doc = DocumentPdf('Bon de réception', reception.numero)
    _entete_document(doc, 'Réception', reception.numero, reception.date_reception)
    doc.paragraphe(f'<b>Commande :</b> {reception.commande.numero}')
    lignes = [
        [l.medicament.nom, l.numero_lot, _date(l.date_peremption),
         str(l.quantite), f'{l.sous_total} Ar']
        for l in reception.lignes.select_related('medicament')
    ]
    doc.tableau(
        [['Médicament', 'Lot', 'Péremption', 'Qté', 'Montant']] + lignes,
        largeurs=[150, 65, 70, 35, 75],
    )
    doc.paragraphe(f'<b>Total :</b> {reception.total} Ar')
    return doc.reponse(f'bon-reception-{reception.numero}')


def generer_rapport_stock():
    doc = DocumentPdf('Rapport de stock', f'Édité le {_date(timezone.localdate())}')
    lignes = []
    for medicament in Medicament.objects.filter(statut=Medicament.STATUT_ACTIF):
        lignes.append([
            medicament.nom, medicament.categorie.nom,
            str(medicament.stock_disponible), str(medicament.seuil_alerte),
            'ALERTE' if medicament.est_sous_le_seuil else 'OK',
        ])
    doc.tableau(
        [['Médicament', 'Catégorie', 'Stock', 'Seuil', 'État']] + lignes,
        largeurs=[180, 100, 50, 50, 60],
    )
    return doc.reponse('rapport-stock')


def generer_rapport_ventes(debut, fin):
    doc = DocumentPdf('Rapport des ventes', f'Du {_date(debut)} au {_date(fin)}')
    ventes = Vente.objects.filter(date__date__range=(debut, fin))
    lignes = [
        [v.numero, _date(v.date), str(v.utilisateur or '-'),
         v.get_statut_display(), f'{v.total} Ar']
        for v in ventes.select_related('utilisateur')
    ]
    total = sum((v.total for v in ventes), 0)
    doc.tableau([['Numéro', 'Date', 'Utilisateur', 'Statut', 'Total']] + lignes)
    doc.paragraphe(f'<b>Chiffre d affaires (ventes validées) :</b> {total} Ar')
    doc.paragraphe(
        'Les encaissements correspondent aux seuls paiements confirmés ; '
        'la marge commerciale n est pas un bénéfice net.'
    )
    return doc.reponse('rapport-ventes')


def generer_rapport_achats(debut, fin):
    doc = DocumentPdf('Rapport des achats', f'Du {_date(debut)} au {_date(fin)}')
    receptions = ReceptionAchat.objects.filter(date_reception__range=(debut, fin))
    lignes = [
        [r.numero, _date(r.date_reception), r.commande.fournisseur.nom, f'{r.total} Ar']
        for r in receptions.select_related('commande__fournisseur')
    ]
    doc.tableau([['Réception', 'Date', 'Fournisseur', 'Total']] + lignes)
    return doc.reponse('rapport-achats')


def generer_rapport_peremptions():
    doc = DocumentPdf('Lots proches de la péremption', f'Édité le {_date(timezone.localdate())}')
    lots = LotStock.objects.filter(quantite__gt=0).select_related('medicament')
    lignes = [
        [l.medicament.nom, l.numero_lot, _date(l.date_peremption),
         str(l.quantite), 'PÉRIMÉ' if l.est_perime else ('BLOQUÉ' if l.est_bloque else 'OK')]
        for l in lots
    ]
    doc.tableau(
        [['Médicament', 'Lot', 'Péremption', 'Qté', 'État']] + lignes,
        largeurs=[170, 80, 80, 40, 60],
    )
    return doc.reponse('rapport-peremptions')
