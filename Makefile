.DEFAULT_GOAL := help

.PHONY: help build up down logs check test seed roles verify backup shell

RUN = docker compose run --rm web

help: ## Affiche les commandes disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

build: ## Construit l'image web
	docker compose build

up: ## Démarre la base et l'application
	docker compose up -d

down: ## Arrête les conteneurs
	docker compose down

logs: ## Affiche les logs du serveur
	docker compose logs -f web

check: ## Vérifie la configuration Django
	$(RUN) python manage.py check

test: ## Lance la suite de tests
	$(RUN) python manage.py test

roles: ## (Re)crée les groupes et permissions
	$(RUN) python manage.py setup_roles

seed: ## Charge les données fictives
	$(RUN) python manage.py seed_demo

migrate: ## Applique les migrations
	$(RUN) python manage.py migrate --noinput

verify: ## Contrôle la cohérence des stocks
	$(RUN) python manage.py verifier_stock

backup: ## Crée une sauvegarde horodatée
	$(RUN) python manage.py sauvegarder

shell: ## Ouvre un shell Django
	$(RUN) python manage.py shell
