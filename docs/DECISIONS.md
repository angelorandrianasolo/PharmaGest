# Décisions techniques et limites assumées

Ce document consigne les arbitrages effectués pendant la réalisation, afin que le projet reste
compréhensible et maintenable.

## 1. Docker via Podman sur cette machine

La machine hôte utilise **Podman rootless** ; le paquet `podman-docker` fournit l'alias
`docker` et `docker-compose` est installé. Les commandes `docker compose ...` fonctionnent
donc normalement, à condition que le socket utilisateur soit actif :

```bash
systemctl --user start podman.socket
```

SELinux étant en mode `Enforcing`, le montage du code source est déclaré `.:/app:z` dans
`docker-compose.yml` (le suffixe `:z` relabelle le volume pour le conteneur).

Le `Dockerfile` s'exécute en root dans le conteneur : avec un montage rootless depuis
`/home/angelo` (répertoire en mode `700`), forcer `USER 1000:1000` empêchait l'accès au code.

## 2. PostgreSQL dès le développement

Le cahier propose SQLite en développement et PostgreSQL en production. Nous avons retenu
**PostgreSQL dans les deux cas** pour éviter les divergences de comportement. C'est notamment
nécessaire pour `SELECT FOR UPDATE`, utilisé pour verrouiller les lots et les ventes pendant
les opérations atomiques.

## 3. Achats : deux étapes distinctes

`CommandeAchat` ne touche jamais au stock. Seule `ReceptionAchat` crée des `LotStock` et des
`MouvementStock`, via `stock.services.enregistrer_reception`. Une réception ne peut pas dépasser
la quantité commandée et un lot périmé ne peut pas être réceptionné. Cela satisfait RG04/RG05.

## 4. FEFO automatique et lots exclus

`stock.allocation.allouer_lots_fefo` trie les lots par `date_peremption` croissante et exclut
les lots `est_bloque=True`, périmés ou à quantité nulle. La sélection manuelle du lot n'est pas
proposée : c'est un choix volontaire pour garantir RG08 sans dépendre de l'utilisateur.

**Limite assumée** : si le métier souhaite permettre un choix manuel (par exemple pour une
substitution), il faudra ajouter une option explicite avec justification obligatoire et
contrôle du pharmacien.

## 5. Ventes atomiques et idempotence

`ventes.services.creer_vente` est `@transaction.atomic` : allocation FEFO, création de la
vente, des lignes, du paiement, consommation des lots et écriture du journal sont indivisibles.
Une clé `idempotency_key` (UUID) empêche une double validation. Les prix sont copiés dans
`LigneVente.prix_unitaire` : une modificationtarifaire ultérieure ne change pas l'historique.

## 6. Paiement mobile money

Le paiement n'est jamais supposé réussi : une vente mobile money est créée en attente et
n'est confirmée qu'après saisie d'une référence de transaction. Seuls les paiements `confirme`
entrent dans le calcul des encaissements du tableau de bord.

## 7. Pas de suppression destructive

- Médicament : `statut=archive`, restaurable, toujours lié à ses lignes historiques.
- Fournisseur : `actif=False`.
- Commande : `statut=annulee` seulement si aucune réception.
- Vente : annulation par `RetourVente` compensatoires et remboursement du paiement.

Cela protège l'historique (RG10) et simplifie la traçabilité.

## 8. Rôles et permissions

Les rôles sont des groupes Django ; `core/permissions.py` est la source de vérité et
`setup_roles` applique la matrice. Les vues utilisent `PermissionRequiredMixin` ou
`AnyPermissionRequiredMixin`, et le menu masque les liens non autorisés. Le masquage de l'interface
n'est jamais la seule protection : chaque vue vérifie la permission côté serveur.

## 9. Sauvegarde

`sauvegarder` exporte un JSON horodaté dans `backups/` (gitignore). `restaurer` crée d'abord une
sauvegarde de sécurité, puis recharge dans une transaction. Le test `tests/test_sauvegarde.py`
vérifie qu'une donnée supprimée est bien récupérée.

**Limite assumée** : pour une très grosse base, préférer `pg_dump`/`pg_restore` et un stockage
hors du serveur applicatif (chiffré, avec rotation et test régulier).

## 10. Points à traiter avant une exploitation réelle

Le logiciel est un support de gestion, **pas un outil de décision clinique** :

- vérifier les exigences réglementaires locales (délivrance, ordonnances, traçabilité des lots,
  facturation, conservation des documents, protection des données personnelles) ;
- ajouter un contrôle explicite du pharmacien pour les médicaments soumis à prescription ;
- prévoir une procédure de purge/conservation conforme pour les données personnelles ;
- générer une vraie `SECRET_KEY`, désactiver `DEBUG`, configurer HTTPS et les origines CSRF ;
- mettre en place des sauvegardes automatiques hors site et un plan de reprise testé ;
- adapter les mentions légales et fiscales des PDF (les modèles actuels sont volontairement
  génériques).

Ces points sont explicitement demandés en section 12 du cahier des charges.
