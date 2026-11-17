# PharmaGest

Application web de gestion de pharmacie développée avec **Django 5.2**, conteneurisée avec
**Docker Compose**.

Fonctionnalités principales :

- catalogue des médicaments avec catégories, recherche, pagination, photo contrôlée (Pillow) et archivage non destructif ;
- gestion des fournisseurs et des clients ;
- achats en deux temps : **commande** puis **réception** (seule la réception crée du stock) ;
- stocks par lots avec **FEFO** (première péremption, première sortie), blocage et inventaire ;
- caisse avec ventes atomiques, paiements espèces ou mobile money, retours compensatoires et annulations tracées ;
- tableau de bord, alertes de rupture/péremption et documents **PDF ReportLab** ;
- rôles et permissions, journal d'audit, sauvegarde/restauration ;
- jeu de données fictives et 34 tests automatisés.

---

## 1. Prérequis

- Docker (ou Podman avec l'alias `docker`) et le plugin `docker compose`.
- Git.
- Aucune installation Python locale n'est nécessaire : tout tourne dans le conteneur.

> Sur Fedora avec Podman rootless, démarrer le socket si besoin :
> `systemctl --user start podman.socket`.
> Le montage `.:/app:z` du `docker-compose.yml` est indispensable avec SELinux en mode `Enforcing`.

## 2. Installation et démarrage

```bash
git clone <ce-depot> PharmaGest
cd PharmaGest
cp .env.example .env        # à adapter avant toute mise en production
docker compose build
docker compose up -d
```

Initialiser la base, les rôles et les données de démonstration :

```bash
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py setup_roles
docker compose run --rm web python manage.py seed_demo
```

L'application est alors disponible sur <http://localhost:8000>.

### Comptes de démonstration

Mot de passe unique : **`pharma123`** (à changer impérativement hors démonstration).

| Identifiant  | Rôle                     | Accès principal                         |
|--------------|--------------------------|-----------------------------------------|
| `admin`      | Administrateur           | Tout (superutilisateur)                 |
| `pharmacien` | Pharmacien responsable   | Validation, réceptions, rapports        |
| `stock`      | Gestionnaire de stock    | Commandes, réceptions, inventaires      |
| `caissier`   | Caissier                 | Caisse, clients, paiements, retours     |
| `gestion`    | Responsable de gestion   | Consultation et rapports                |

## 3. Commandes courantes

```bash
# Vérification du projet
docker compose run --rm web python manage.py check

# Tests automatisés (34 tests)
docker compose run --rm web python manage.py test

# Contrôle de cohérence stock <> mouvements
docker compose run --rm web python manage.py verifier_stock

# Sauvegarde et restauration
docker compose run --rm web python manage.py sauvegarder
docker compose run --rm web python manage.py restaurer backups/pharmagest-....json

# Logs et arrêt
docker compose logs -f web
docker compose down
```

Un `Makefile` propose des raccourcis : `make up`, `make test`, `make seed`, `make check`, `make backup`.

## 4. Structure du projet

```
config/            configuration Django (settings, urls, wsgi, asgi)
core/              socle : audit, permissions, utilitaires, mixins, sauvegarde
utilisateurs/      comptes, rôles, commandes setup_roles et seed_demo
medicaments/       catégories, médicaments, photos, recherche, archivage
fournisseurs/      fiches fournisseurs
clients/           fiches clients
achats/            commandes et réceptions (services transactionnels)
stock/             lots, mouvements, FEFO, corrections, verifier_stock
ventes/            caisse, paiements, retours, annulations
rapports/          tableau de bord et PDF ReportLab
templates/         interface en français (identité « Ordonnance »)
static/css/        système de design (variables, typographie, animations)
static/images/     logo, maquettes du cahier et visuels médicaments de démonstration
media/             photos téléversées (volume Docker)
backups/           sauvegardes locales (ignorées par Git)
tests/             suite de tests Django
docs/              conception, décisions, guide utilisateur
```

## 5. Configuration

Toutes les valeurs sensibles passent par les variables d'environnement (voir `.env.example`) :
`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, identifiants PostgreSQL,
`SECURE_SSL_REDIRECT`, `PHARMACIE_NOM`. Le fichier `.env` n'est jamais versionné.

En production : générer une vraie `SECRET_KEY`, passer `DEBUG=false`, activer
`SECURE_SSL_REDIRECT=true` derrière un proxy HTTPS, restreindre `ALLOWED_HOSTS` et
renseigner `CSRF_TRUSTED_ORIGINS`.

## 6. Sécurité et exploitation réelle

- CSRF activé sur tous les formulaires ; permissions vérifiées dans chaque vue.
- Validation serveur des prix et quantités (formulaires + contraintes PostgreSQL).
- Images vérifiées par PIL (type réel, format autorisé, taille maximale 5 Mo).
- Transactions atomiques et `SELECT FOR UPDATE` sur les opérations de stock.
- Aucune suppression destructive : archivage, désactivation, retours compensatoires.
- Journal d'audit des opérations sensibles (auteur, date, IP, détail).
- Clé d'idempotence sur les ventes : une double validation ne décrémente pas deux fois le stock.

> **Important** : la présence d'un médicament dans la base ne constitue pas une autorisation
> de délivrance. Les règles pharmaceutiques locales (prescription, contrôle du pharmacien,
> conservation des documents, données personnelles, fiscalité) doivent être vérifiées par un
> professionnel avant toute exploitation réelle. Voir `docs/DECISIONS.md`.

## 7. Documentation

- `docs/CONCEPTION.md` : MCD, MLD, diagrammes d'états et de séquence, matrice des rôles.
- `docs/DECISIONS.md` : choix techniques et limites assumées.
- `docs/GUIDE_UTILISATION.md` : parcours utilisateur pas à pas.

## 8. Interface et visuels

L'interface adopte une direction « ordonnance » : vert profond et ambre sur un fond de
papeterie chaude, typographie éditoriale (Fraunces + DM Sans), barre latérale, cartes aérées
et animations d'entrée discrètes. Le CSS est centralisé dans `static/css/app.css` via des
variables CSS ; Bootstrap reste utilisé pour la grille et les formulaires.

Les images fournies dans le cahier des charges ont été extraites du PDF et versionnées dans
`static/images/maquettes/` : bannière de couverture, aperçu général, tableau de bord,
catalogue des médicaments, caisse, stocks et graphiques. Elles servent de références visuelles
sur l'accueil et sur l'écran de connexion. Les illustrations de `static/images/medicaments/`
sont des visuels de démonstration : dès qu'une photo réelle est téléversée sur un médicament,
c'est elle qui est affichée.
