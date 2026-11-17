"""Rôles et matrice des permissions.

Les permissions sont celles de Django (codenames `app.action_modele`).
Un utilisateur peut cumuler plusieurs rôles via les groupes Django ; le champ
`role` du modèle Utilisateur sert d'étiquette principale dans l'interface.
"""

ADMINISTRATEUR = "administrateur"
PHARMACIEN = "pharmacien"
GESTIONNAIRE_STOCK = "gestionnaire_stock"
CAISSIER = "caissier"
RESPONSABLE_GESTION = "responsable_gestion"
INSCRIT = "inscrit"

ROLES = [
    (ADMINISTRATEUR, "Administrateur"),
    (PHARMACIEN, "Pharmacien responsable"),
    (GESTIONNAIRE_STOCK, "Gestionnaire de stock"),
    (CAISSIER, "Caissier"),
    (RESPONSABLE_GESTION, "Responsable de gestion"),
    (INSCRIT, "Utilisateur inscrit"),
]

COMMUN = [
    "view_medicament",
    "view_categorie",
]

ROLE_PERMISSIONS = {
    ADMINISTRATEUR: ["*"],
    PHARMACIEN: COMMUN
    + [
        "add_medicament",
        "change_medicament",
        "view_lotstock",
        "add_lotstock",
        "change_lotstock",
        "view_mouvementstock",
        "view_commandeachat",
        "valider_commande",
        "receptionner_commande",
        "view_vente",
        "annuler_vente",
        "valider_retour",
        "confirmer_paiement",
        "consulter_rapports",
        "view_journalaudit",
    ],
    GESTIONNAIRE_STOCK: COMMUN
    + [
        "add_medicament",
        "change_medicament",
        "add_categorie",
        "change_categorie",
        "add_fournisseur",
        "change_fournisseur",
        "view_fournisseur",
        "add_commandeachat",
        "change_commandeachat",
        "view_commandeachat",
        "valider_commande",
        "receptionner_commande",
        "add_lotstock",
        "change_lotstock",
        "view_lotstock",
        "view_mouvementstock",
        "consulter_rapports",
    ],
    CAISSIER: COMMUN
    + [
        "add_client",
        "view_client",
        "add_vente",
        "view_vente",
        "valider_vente",
        "add_paiement",
        "view_paiement",
        "confirmer_paiement",
        "add_retourvente",
        "view_retourvente",
    ],
    RESPONSABLE_GESTION: COMMUN
    + [
        "view_client",
        "view_fournisseur",
        "view_commandeachat",
        "view_vente",
        "view_paiement",
        "view_retourvente",
        "view_mouvementstock",
        "consulter_rapports",
        "view_journalaudit",
    ],
    # Un compte créé via le formulaire public n'obtient qu'un accès en lecture
    # au catalogue, dans l'attente de son activation par un administrateur.
    INSCRIT: list(COMMUN),
}


def codenames_du_role(role: str) -> list[str]:
    """Retourne les codenames attachés à un rôle (`*` = toutes les permissions)."""
    return list(ROLE_PERMISSIONS.get(role, COMMUN))
