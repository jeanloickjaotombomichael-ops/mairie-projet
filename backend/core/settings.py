"""Réglages Django du projet Mairy Project.

Tous les réglages sensibles sont lus depuis des variables d'environnement
(éventuellement chargées depuis un fichier ``.env`` si python-dotenv est installé).
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv est optionnel
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


DEBUG = env_bool('DJANGO_DEBUG', False)

# Vrai quand on lance « python manage.py test » : évite d'exiger des clés réelles.
TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

_DEV_SECRET_KEY = 'dev-only-insecure-secret-key-change-me'
_DEV_SIGNING_KEY = 'dev-only-insecure-document-signing-key-change-me'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
DOCUMENT_SIGNING_KEY = os.environ.get('DOCUMENT_SIGNING_KEY', '')

if DEBUG or TESTING:
    SECRET_KEY = SECRET_KEY or _DEV_SECRET_KEY
    DOCUMENT_SIGNING_KEY = DOCUMENT_SIGNING_KEY or _DEV_SIGNING_KEY
else:
    if not SECRET_KEY:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY doit être défini quand DJANGO_DEBUG est désactivé."
        )
    if not DOCUMENT_SIGNING_KEY:
        raise ImproperlyConfigured(
            "DOCUMENT_SIGNING_KEY doit être défini quand DJANGO_DEBUG est désactivé."
        )

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

# URL publique du frontend React (utilisée dans les QR codes).
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173').strip().rstrip('/')

# Limitation de débit des demandes d'accès agent : (nombre de requêtes, fenêtre en secondes).
AGENT_REQUEST_RATE_LIMIT = (10, 3600)

# Espace usager : limitation de débit (nombre de requêtes, fenêtre en secondes).
DOSSIER_RATE_LIMIT = (30, 3600)  # par utilisateur Clerk
CONTACT_RATE_LIMIT = (10, 3600)  # par adresse IP

# Authentification Clerk (jeton de session envoyé par le frontend en « Bearer »).
# Renseignez CLERK_PUBLISHABLE_KEY (la même clé que VITE_CLERK_PUBLISHABLE_KEY) :
# l'émetteur (issuer) et l'URL des clés publiques en sont déduits. À défaut,
# fournissez CLERK_ISSUER (et éventuellement CLERK_JWKS_URL).
CLERK_PUBLISHABLE_KEY = os.environ.get('CLERK_PUBLISHABLE_KEY', '').strip()
CLERK_ISSUER = os.environ.get('CLERK_ISSUER', '').strip().rstrip('/')
CLERK_JWKS_URL = os.environ.get('CLERK_JWKS_URL', '').strip()
# Origines autorisées dans la revendication « azp » du jeton (optionnel).
CLERK_AUTHORIZED_PARTIES = [item.rstrip('/') for item in env_list('CLERK_AUTHORIZED_PARTIES')]

INSTALLED_APPS = [
    'core.apps.MairyAdminConfig',  # admin Django avec le tableau de bord Mairy
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'documents.apps.DocumentsConfig',
    'espace.apps.EspaceConfig',
    'agents.apps.AgentsConfig',
    'messagerie.apps.MessagerieConfig',
    'fichiers.apps.FichiersConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

if os.environ.get('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['POSTGRES_DB'],
            'USER': os.environ.get('POSTGRES_USER', ''),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'mairy-project',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr'

# Langues de l'administration et de l'espace agent (sélecteur en haut de chaque page).
# Les textes sources sont en français ; traductions dans locale/<langue>/LC_MESSAGES/django.po.
LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
    ('mg', 'Malagasy'),
]
# locale_django : chaînes de l'administration Django traduites en malagasy (Django n'en fournit pas).
LOCALE_PATHS = [BASE_DIR / 'locale', BASE_DIR / 'locale_django']

# Django ne connaît pas le malgache : on le déclare pour ses outils de langue.
from django.conf.locale import LANG_INFO  # noqa: E402

LANG_INFO.setdefault('mg', {'bidi': False, 'code': 'mg', 'name': 'Malagasy', 'name_local': 'Malagasy'})
TIME_ZONE = 'Indian/Antananarivo'
USE_I18N = True
USE_TZ = True

# Connexion commune aux administrateurs et aux agents (redirection selon le rôle).
LOGIN_URL = 'connexion'

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS : le frontend React tourne sur une autre origine en développement.
CORS_ALLOWED_ORIGINS = [
    origin.rstrip('/')
    for origin in env_list(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173',
    )
]

# Cookies sécurisés hors développement.
SESSION_COOKIE_SECURE = not (DEBUG or TESTING)
CSRF_COOKIE_SECURE = not (DEBUG or TESTING)

# Envoi des e-mails (Mail des administrateurs et des agents vers les adresses extérieures).
# Sans EMAIL_HOST, les messages vers l'extérieur ne sont pas envoyés (ils restent dans « Messages envoyés »).
EMAIL_HOST = os.environ.get('EMAIL_HOST', '').strip()
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'webmaster@localhost')
