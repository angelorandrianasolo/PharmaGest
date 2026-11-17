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
- inscription publique (compte à activer), profil consultable et modifiable avec photo de profil et confirmation du mot de passe ;
- jeu de données fictives et 59 tests automatisés.

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

Un visiteur peut créer un compte depuis la page de connexion (`Créer un compte`). Le compte est
créé avec le rôle **Utilisateur inscrit** (lecture du catalogue) et reste inactif jusqu'à son
activation par un administrateur dans `Utilisateurs`. Le réglage `INSCRIPTION_ACTIVATION_AUTO=True`
permet de l'activer immédiatement (démonstration uniquement).

Chaque utilisateur dispose d'une page **Mon profil** (menu latéral) : consultation de son identité,
de ses coordonnées et de son rôle, modification des informations et de la photo de profil après
confirmation du mot de passe actuel, et changement de mot de passe dédié. La suppression de la photo
nécessite également cette confirmation.

## 3. Commandes courantes

```bash
# Vérification du projet
docker compose run --rm web python manage.py check

# Tests automatisés (59 tests)
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
static/images/     logo, hero original, visuels médicaments et maquettes du cahier
media/             photos téléversées (volume Docker)
backups/           sauvegardes locales (ignorées par Git)
tests/             suite de tests Django
docs/              conception, décisions, guide utilisateur
docker-compose.prod.yml  configuration Docker de production (autonome)
deploy/Caddyfile         reverse proxy HTTPS, certificats et médias
```

## 5. Configuration

Toutes les valeurs sensibles passent par les variables d'environnement (voir `.env.example`) :
`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, identifiants PostgreSQL,
`SECURE_SSL_REDIRECT`, `PHARMACIE_NOM`. Le fichier `.env` n'est jamais versionné.

En production : générer une vraie `SECRET_KEY`, passer `DEBUG=false`, activer
`SECURE_SSL_REDIRECT=true` derrière un proxy HTTPS, restreindre `ALLOWED_HOSTS` et
renseigner `CSRF_TRUSTED_ORIGINS`.

Le modèle dédié est `.env.prod.example` : le copier vers `.env.prod` puis renseigner toutes
les valeurs. Ce fichier sert à la fois à la substitution des variables par Docker Compose
(option `--env-file` utilisée par les cibles `prod-*`) et à l'environnement du conteneur
Django. Il n'est jamais versionné.

## 6. Déploiement de production

La configuration de production est **autonome** : `docker-compose.prod.yml` ne surcharge pas
le fichier de développement, ne monte pas le code source de l'hôte et n'expose pas le port
8000. Gunicorn sert Django sur le réseau interne et Caddy (profil `tls`) termine le HTTPS.

1. Copier le modèle d'environnement et adapter toutes les valeurs :

   ```bash
   cp .env.prod.example .env.prod
   ```

   Renseigner au minimum `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (en `https://`),
   `PHARMAGEST_DOMAIN` et `POSTGRES_PASSWORD`.

2. Générer une clé secrète unique et la coller dans `.env.prod` (variable `SECRET_KEY`) :

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

3. Construire l'image puis démarrer la pile avec le reverse proxy :

   ```bash
   make prod-build
   make prod-up
   ```

   `prod-up` active le profil `tls` : Caddy écoute sur les ports 80 et 443, obtient un
   certificat **Let's Encrypt** pour `PHARMAGEST_DOMAIN` et le renouvelle automatiquement.

4. Faire pointer le DNS de `PHARMAGEST_DOMAIN` vers l'adresse IP du serveur et ouvrir les
   ports 80 et 443. La délivrance du certificat nécessite un domaine accessible depuis
   Internet.

5. Les photos téléversées sont écrites dans le volume `media_data`, monté en lecture seule
   dans Caddy : `/media/*` est servi directement par le reverse proxy, sans passer par Django.

6. Sauvegarder régulièrement les volumes nommés `postgres_data`, `media_data`, `caddy_data`
   et `caddy_config`. Par exemple, pour la base :

   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml exec db \
     pg_dump -U pharmagest pharmagest > sauvegarde.sql
   ```

   Une sauvegarde applicative est aussi disponible via
   `docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py sauvegarder`.

La pile s'arrête avec `make prod-down` et se surveille avec `make prod-logs`.

## 7. Sécurité et exploitation réelle

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

## 8. Documentation

- `docs/CONCEPTION.md` : MCD, MLD, diagrammes d'états et de séquence, matrice des rôles.
- `docs/DECISIONS.md` : choix techniques et limites assumées.
- `docs/GUIDE_UTILISATION.md` : parcours utilisateur pas à pas.

## 9. Interface et visuels

L'interface adopte une direction « ordonnance » : vert profond et ambre sur un fond de
papeterie chaude, typographie éditoriale (Fraunces + DM Sans), barre latérale, cartes aérées
et animations d'entrée discrètes. Le CSS est centralisé dans `static/css/app.css` via des
variables CSS ; Bootstrap reste utilisé pour la grille et les formulaires.

L'accueil affiche des **données réelles** : indicateurs de la journée (ventes, chiffre
d'affaires, réceptions, alertes), dernières ventes, lots proches de la péremption et paiements
en attente, le tout filtré selon les permissions de l'utilisateur. La photo d'accueil
(`static/images/maquettes/couverture.jpg`) est conservée à côté du titre principal ; l'ancien
bloc « Références visuelles du cahier des charges » qui se trouvait à côté des alertes de stock
a, lui, été supprimé.

Un bouton **Retour** est disponible sur toutes les pages (dans la barre supérieure pour les
pages connectées, au-dessus du formulaire pour les pages publiques) : il revient à la page
précédente et replie sur l'accueil en l'absence d'historique.

La page de connexion est une carte centrée : illustration originale en bandeau
(`static/images/hero-pharmacie.svg`), formulaire avec autocomplétion et icônes de champ, accès
balisé « mot de passe oublié » et lien vers l'inscription. Les pages d'inscription reprennent la
même présentation centrée. Le menu latéral propose les entrées **Accueil** et **Mon profil**, et un
visiteur non connecté est systématiquement redirigé vers la connexion.

Les maquettes extraites du cahier restent archivées dans `static/images/maquettes/` comme
références de conception. Les illustrations de `static/images/medicaments/` sont des visuels
de démonstration : dès qu'une photo réelle est téléversée sur un médicament, c'est elle qui est
affichée.
