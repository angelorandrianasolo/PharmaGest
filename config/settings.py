"""Configuration du projet PharmaGest.

Toutes les valeurs sensibles ou dépendantes de l'environnement sont lues
depuis les variables d'environnement (voir `.env.example`).
"""

import os
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# En production on utilise `.env.prod` (voir docker-compose.prod.yml) plutôt
# que le fichier de développement ; les variables d'environnement du
# conteneur restent prioritaires sur le contenu du fichier.
env.read_env(BASE_DIR / os.environ.get("DJANGO_ENV_FILE", ".env"))

DEBUG = env.bool("DEBUG", default=True)
SECRET_KEY = env("SECRET_KEY", default="development-only-key-change-me")
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "0.0.0.0", "web"] if DEBUG else [],
)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not DEBUG:
    # Refuser de démarrer en production avec la configuration de développement.
    if (
        SECRET_KEY == "development-only-key-change-me"
        or "remplacez" in SECRET_KEY.lower()
        or len(SECRET_KEY) < 40
    ):
        raise ImproperlyConfigured(
            "SECRET_KEY doit être remplacée par une valeur secrète d'au moins 40 caractères."
        )
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS doit contenir les noms d'hôte autorisés en production."
        )
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS doit contenir l'origine HTTPS en production."
        )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Applications du projet
    "core",
    "utilisateurs",
    "medicaments",
    "fournisseurs",
    "clients",
    "achats",
    "stock",
    "ventes",
    "rapports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.parametres",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

AUTH_USER_MODEL = "utilisateurs.Utilisateur"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Indian/Antananarivo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
PHARMACIE_NOM = env("PHARMACIE_NOM", default="Pharmacie PharmaGest")

LOGIN_URL = "utilisateurs:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "utilisateurs:login"

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="pharmagest@localhost")

# Sécurité :activable sans modifier le code (derrière un proxy HTTPS en production).
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s : %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
