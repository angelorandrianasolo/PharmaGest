# Guide d'utilisation PharmaGest

## 1. Connexion

Ouvrez <http://localhost:8000> puis saisissez votre identifiant et votre mot de passe.
Le menu affiche uniquement les modules auxquels votre rôle donne accès.

Comptes de démonstration (mot de passe `pharma123`) : `admin`, `pharmacien`, `stock`,
`caissier`, `gestion`. Le mot de passe se modifie via la page dédiée.

## 2. Tableau de bord

Page d'accueil des rôles autorisés : médicaments actifs, ventes et chiffre d'affaires du jour,
encaissements confirmés, marge commerciale (avant charges), graphiques des 7 derniers jours,
stocks faibles, péremptions à 30 jours, lots périmés et produits les plus vendus.

Des boutons permettent de télécharger les rapports PDF : stock, péremptions, ventes et achats
(30 jours par défaut ou période choisie avec les champs date).

## 3. Médicaments et catégories

1. `Médicaments` → `Ajouter un médicament`.
2. Renseigner nom, générique, catégorie, forme, dosage, laboratoire, code-barres, prix d'achat,
   prix de vente, seuil d'alerte et photo.
3. La photo est contrôlée : JPEG/PNG/WEBP/GIF, 5 Mo maximum.
4. La liste est recherchable par nom ou code-barres, filtrable par catégorie, triable et paginée.
5. `Modifier` met à jour les informations. `Archiver` retire le produit de la vente sans effacer
   son historique ; `Restaurer` le réactive. Une confirmation est demandée.

## 4. Fournisseurs et clients

Les fiches se créent, se modifient et se recherchent. Un fournisseur peut être désactivé sans
perdre ses commandes. Les données clients sont limitées au strict nécessaire (nom, téléphone,
e-mail, adresse).

## 5. Achats et réceptions

1. `Achats` → `Nouvelle commande` : choisir le fournisseur et ajouter les lignes
   (médicament, quantité, prix unitaire), puis créer.
2. Sur le détail de la commande, cliquer sur `Valider` (rôle pharmacien ou gestionnaire).
3. Cliquer sur `Réceptionner` : indiquer pour chaque ligne le **numéro de lot**, la
   **date de péremption**, la quantité reçue et le prix unitaire, puis valider.
4. Le stock augmente immédiatement et un bon de réception PDF est disponible.
5. Une réception partielle est possible : la commande passe en
   `Partiellement réceptionnée` puis `Entièrement réceptionnée`.

> Une commande seule ne modifie jamais le stock. Une quantité réceptionnée supérieure à la
> quantité commandée, ou un lot déjà périmé, est refusé.

## 6. Stocks

`Stocks` affiche les lots avec leur état (délivrable, périmé, bloqué, épuisé).
Le filtre `Péremptions uniquement` et la recherche par médicament ou numéro de lot facilitent
le suivi.

- `Historique des mouvements` liste toutes les entrées, sorties, corrections et retours avec
  référence, auteur et date.
- `Correction / inventaire` permet d'ajuster une quantité en saisissant un motif obligatoire.
- `Bloquer` / `Débloquer` retire temporairement un lot de la vente.

La commande `verifier_stock` contrôle que chaque lot correspond exactement à la somme de ses
mouvements.

## 7. Caisse et ventes

1. `Caisse` → choisir le client (facultatif) et le mode de paiement.
2. Ajouter les médicaments et les quantités. Le lot est choisi automatiquement selon la méthode
   **FEFO** : le lot dont la date de péremption est la plus proche est délivré en premier.
   Les lots périmés ou bloqués sont exclus.
3. `Valider la vente` : le stock est décrémenté dans une transaction atomique. Si le stock est
   insuffisant, la vente est refusée sans aucune écriture partielle.

### Paiements

- **Espèces** : la vente est immédiatement `Confirmée` et le paiement `Confirmé`.
- **Mobile money** : la vente reste `En attente de paiement`. Sur le détail de la vente, cliquer
  sur `Confirmer`, saisir la référence de la transaction, puis valider. Seuls les paiements
  confirmés comptent comme encaissements.

### Retours et annulations

Sur le détail d'une vente, chaque ligne propose `Retour` : saisir la quantité, le motif et
choisir la réintégration en stock. Un lot périmé ou bloqué n'est pas réintégré.
`Annuler la vente` génère des retours compensatoires pour toutes les lignes et marque les
paiements comme remboursés : aucune vente validée n'est supprimée.

### Documents

Le détail d'une vente propose le **reçu** et la **facture** en PDF. Le détail d'une commande
propose le **bon de commande** et le **bon de réception**.

## 8. Utilisateurs et droits

`Utilisateurs` permet de créer des comptes, choisir le rôle principal, modifier les groupes,
activer/désactiver un compte et changer son mot de passe. Vous ne pouvez pas désactiver votre
propre compte. La matrice des droits est décrite dans `docs/CONCEPTION.md`.

## 9. Sauvegarde et restauration

```bash
docker compose run --rm web python manage.py sauvegarder
docker compose run --rm web python manage.py restaurer backups/pharmagest-....json
```

La restauration crée d'abord une sauvegarde de sécurité et s'exécute dans une transaction.

## 10. En cas d'erreur

Les messages d'erreur métier s'affichent en haut de page (stock insuffisant, lot périmé,
quantité supérieure à la commande, permission refusée). En cas de doute sur le stock, lancer
`python manage.py verifier_stock` dans le conteneur web.
