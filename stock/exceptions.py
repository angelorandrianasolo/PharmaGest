"""Erreurs métier du sous-système stock."""


class ErreurStock(Exception):
    """Classe de base des erreurs de stock."""


class StockInsuffisantError(ErreurStock):
    """La quantité demandée n'est pas disponible en lots délivrables."""


class LotNonDelivrableError(ErreurStock):
    """Le lot demandé est périmé, bloqué ou vide."""
