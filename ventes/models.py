"""Ventes, lignes, paiements et retours."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class Vente(TimeStampedModel):
    STATUT_EN_ATTENTE = 'en_attente_paiement'
    STATUT_CONFIRMEE = 'confirmee'
    STATUT_ANNULEE = 'annulee'
    STATUTS = [
        (STATUT_EN_ATTENTE, 'En attente de paiement'),
        (STATUT_CONFIRMEE, 'Confirmée'),
        (STATUT_ANNULEE, 'Annulée'),
    ]
    MODE_ESPECES = 'especes'
    MODE_MOBILE_MONEY = 'mobile_money'
    MODE_AUTRE = 'autre'
    MODES = [
        (MODE_ESPECES, 'Espèces'),
        (MODE_MOBILE_MONEY, 'Mobile money'),
        (MODE_AUTRE, 'Autre moyen autorisé'),
    ]

    class Meta:
        verbose_name = 'vente'
        verbose_name_plural = 'ventes'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['numero']),
            models.Index(fields=['date']),
        ]
        permissions = [
            ('valider_vente', 'Valider une vente'),
            ('annuler_vente', 'Annuler une vente'),
            ('consulter_rapports', 'Consulter les rapports et statistiques'),
        ]

    numero = models.CharField('numéro', max_length=50, unique=True)
    idempotency_key = models.UUIDField('clé d idempotence', default=uuid.uuid4, unique=True, editable=False)
    client = models.ForeignKey(
        'clients.Client', verbose_name='client', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ventes',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ventes',
    )
    date = models.DateTimeField('date', default=timezone.now, db_index=True)
    statut = models.CharField('statut', max_length=25, choices=STATUTS, default=STATUT_EN_ATTENTE)
    mode_paiement = models.CharField('mode de paiement', max_length=20, choices=MODES, default=MODE_ESPECES)
    total = models.DecimalField('total', max_digits=14, decimal_places=2, default=0)
    note = models.TextField('note', blank=True)

    def __str__(self):
        return f'{self.numero} — {self.total} Ar'

    @property
    def est_confirmee(self):
        return self.statut == self.STATUT_CONFIRMEE


class LigneVente(models.Model):
    """Le prix et le lot sont figés au moment de la vente (RG12)."""

    vente = models.ForeignKey(
        Vente, verbose_name='vente', on_delete=models.CASCADE, related_name='lignes'
    )
    medicament = models.ForeignKey(
        'medicaments.Medicament', verbose_name='médicament', on_delete=models.PROTECT,
        related_name='lignes_vente',
    )
    lot = models.ForeignKey(
        'stock.LotStock', verbose_name='lot', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='lignes_vente',
    )
    numero_lot = models.CharField('numéro de lot', max_length=100, blank=True)
    date_peremption = models.DateField('date de péremption', null=True, blank=True)
    quantite = models.PositiveIntegerField('quantité')
    prix_unitaire = models.DecimalField('prix unitaire appliqué', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'ligne de vente'
        verbose_name_plural = 'lignes de vente'

    def __str__(self):
        return f'{self.medicament} x {self.quantite}'

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire


class Paiement(TimeStampedModel):
    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_CONFIRME = 'confirme'
    STATUT_ECHEC = 'echec'
    STATUT_REMBOURSE = 'rembourse'
    STATUTS = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_CONFIRME, 'Confirmé'),
        (STATUT_ECHEC, 'Échec'),
        (STATUT_REMBOURSE, 'Remboursé'),
    ]

    class Meta:
        verbose_name = 'paiement'
        verbose_name_plural = 'paiements'
        ordering = ['-cree_le']
        permissions = [('confirmer_paiement', 'Confirmer un paiement')]

    vente = models.ForeignKey(
        Vente, verbose_name='vente', on_delete=models.CASCADE, related_name='paiements'
    )
    mode = models.CharField('mode', max_length=20, choices=Vente.MODES, default=Vente.MODE_ESPECES)
    montant = models.DecimalField('montant', max_digits=14, decimal_places=2)
    statut = models.CharField('statut', max_length=20, choices=STATUTS, default=STATUT_EN_ATTENTE)
    reference = models.CharField('référence externe', max_length=120, blank=True)
    confirme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='confirmé par', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='paiements_confirmes',
    )
    confirme_le = models.DateTimeField('confirmé le', null=True, blank=True)

    def __str__(self):
        return f'{self.vente.numero} — {self.get_statut_display()}'


class RetourVente(TimeStampedModel):
    """Opération compensatoire : jamais de suppression d'une vente validée."""

    class Meta:
        verbose_name = 'retour de vente'
        verbose_name_plural = 'retours de vente'
        ordering = ['-date']
        permissions = [('valider_retour', 'Valider un retour')]

    vente = models.ForeignKey(
        Vente, verbose_name='vente', on_delete=models.PROTECT, related_name='retours'
    )
    ligne = models.ForeignKey(
        LigneVente, verbose_name='ligne de vente', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='retours',
    )
    medicament = models.ForeignKey(
        'medicaments.Medicament', verbose_name='médicament', on_delete=models.PROTECT,
        related_name='retours',
    )
    lot = models.ForeignKey(
        'stock.LotStock', verbose_name='lot', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='retours',
    )
    quantite = models.PositiveIntegerField('quantité retournée')
    motif = models.CharField('motif', max_length=250)
    montant_rembourse = models.DecimalField('montant remboursé', max_digits=14, decimal_places=2, default=0)
    remis_en_stock = models.BooleanField('remis en stock', default=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='retours_effectues',
    )
    date = models.DateTimeField('date', default=timezone.now)

    def __str__(self):
        return f'Retour {self.vente.numero} — {self.medicament} x {self.quantite}'
