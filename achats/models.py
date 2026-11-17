"""Commandes d'achat et réceptions de marchandises."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class CommandeAchat(TimeStampedModel):
    STATUT_BROUILLON = 'brouillon'
    STATUT_COMMANDEE = 'commandee'
    STATUT_PARTIELLE = 'partiellement_receptionnee'
    STATUT_TOTALE = 'entierement_receptionnee'
    STATUT_ANNULEE = 'annulee'
    STATUTS = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_COMMANDEE, 'Commandée'),
        (STATUT_PARTIELLE, 'Partiellement réceptionnée'),
        (STATUT_TOTALE, 'Entièrement réceptionnée'),
        (STATUT_ANNULEE, 'Annulée'),
    ]

    class Meta:
        verbose_name = 'commande d achat'
        verbose_name_plural = 'commandes d achat'
        ordering = ['-date_commande']
        permissions = [
            ('valider_commande', 'Valider une commande'),
            ('receptionner_commande', 'Réceptionner une commande'),
            ('annuler_commande', 'Annuler une commande'),
        ]

    numero = models.CharField('numéro', max_length=50, unique=True)
    fournisseur = models.ForeignKey(
        'fournisseurs.Fournisseur', verbose_name='fournisseur',
        on_delete=models.PROTECT, related_name='commandes',
    )
    date_commande = models.DateField('date de commande', default=timezone.localdate)
    statut = models.CharField('statut', max_length=30, choices=STATUTS, default=STATUT_BROUILLON)
    note = models.TextField('note', blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='créé par',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='commandes_creees',
    )

    def __str__(self):
        return f'{self.numero} — {self.fournisseur}'

    @property
    def total(self):
        total = self.lignes.aggregate(
            total=models.Sum(models.F('quantite') * models.F('prix_unitaire'))
        )['total']
        return total or 0

    @property
    def quantite_commandee(self):
        return self.lignes.aggregate(total=models.Sum('quantite'))['total'] or 0

    @property
    def quantite_receptionnee(self):
        total = self.receptions.aggregate(
            total=models.Sum('lignes__quantite')
        )['total']
        return total or 0


class LigneAchat(models.Model):
    commande = models.ForeignKey(
        CommandeAchat, verbose_name='commande', on_delete=models.CASCADE,
        related_name='lignes',
    )
    medicament = models.ForeignKey(
        'medicaments.Medicament', verbose_name='médicament', on_delete=models.PROTECT,
        related_name='lignes_achat',
    )
    quantite = models.PositiveIntegerField('quantité')
    prix_unitaire = models.DecimalField('prix unitaire', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'ligne de commande'
        verbose_name_plural = 'lignes de commande'

    def __str__(self):
        return f'{self.medicament} x {self.quantite}'

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire


class ReceptionAchat(TimeStampedModel):
    numero = models.CharField('numéro', max_length=50, unique=True)
    commande = models.ForeignKey(
        CommandeAchat, verbose_name='commande', on_delete=models.PROTECT,
        related_name='receptions',
    )
    date_reception = models.DateField('date de réception', default=timezone.localdate)
    note = models.TextField('note', blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='créé par',
        null=True, blank=True, on_delete=models.SET_NULL, related_name='receptions_creees',
    )

    class Meta:
        verbose_name = 'réception'
        verbose_name_plural = 'réceptions'
        ordering = ['-date_reception']

    def __str__(self):
        return f'{self.numero} — {self.commande}'

    @property
    def total(self):
        total = self.lignes.aggregate(
            total=models.Sum(models.F('quantite') * models.F('prix_unitaire'))
        )['total']
        return total or 0


class LigneReception(models.Model):
    reception = models.ForeignKey(
        ReceptionAchat, verbose_name='réception', on_delete=models.CASCADE,
        related_name='lignes',
    )
    ligne_achat = models.ForeignKey(
        LigneAchat, verbose_name='ligne de commande', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='lignes_reception',
    )
    medicament = models.ForeignKey(
        'medicaments.Medicament', verbose_name='médicament', on_delete=models.PROTECT,
        related_name='lignes_reception',
    )
    numero_lot = models.CharField('numéro de lot', max_length=100)
    date_peremption = models.DateField('date de péremption')
    quantite = models.PositiveIntegerField('quantité reçue')
    prix_unitaire = models.DecimalField('prix unitaire', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'ligne de réception'
        verbose_name_plural = 'lignes de réception'

    def __str__(self):
        return f'{self.medicament} — lot {self.numero_lot} x {self.quantite}'

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire
