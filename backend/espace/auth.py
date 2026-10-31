"""Authentification par jeton de session Clerk (JWT signé en RS256).

Le frontend envoie ``Authorization: Bearer <jeton>``. Le jeton est vérifié avec
les clés publiques (JWKS) de l'instance Clerk ; l'identifiant de l'utilisateur
est la revendication ``sub``. Le jeton n'est jamais journalisé.
"""
import base64
import binascii
from functools import wraps

import jwt
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from documents.views import json_error

CLOCK_LEEWAY_SECONDS = 10


class AuthNotConfigured(Exception):
    """Aucun émetteur Clerk n'est configuré côté serveur."""


class InvalidToken(Exception):
    """Jeton absent, mal formé, expiré, ou émis par un autre émetteur."""


def issuer_from_publishable_key(publishable_key):
    """Déduit l'émetteur Clerk (``https://<hôte>``) de la clé publique.

    La clé a la forme ``pk_test_<base64>`` ou ``pk_live_<base64>`` ; le contenu
    décodé est ``<hôte>$``. Retourne ``''`` si la clé est absente ou illisible.
    """
    parts = (publishable_key or '').strip().split('_', 2)
    if len(parts) != 3 or parts[0] != 'pk' or not parts[2]:
        return ''
    encoded = parts[2]
    encoded += '=' * (-len(encoded) % 4)
    try:
        host = base64.b64decode(encoded).decode('utf-8')
    except (binascii.Error, ValueError):  # UnicodeDecodeError est un ValueError
        return ''
    host = host.rstrip('$').strip()
    if not host or '.' not in host or any(char.isspace() for char in host):
        return ''
    return f'https://{host}'


def get_issuer():
    """Émetteur attendu : CLERK_ISSUER, sinon déduit de CLERK_PUBLISHABLE_KEY."""
    configured = (getattr(settings, 'CLERK_ISSUER', '') or '').strip().rstrip('/')
    if configured:
        return configured
    return issuer_from_publishable_key(getattr(settings, 'CLERK_PUBLISHABLE_KEY', ''))


def get_jwks_url():
    configured = (getattr(settings, 'CLERK_JWKS_URL', '') or '').strip()
    if configured:
        return configured
    issuer = get_issuer()
    return f'{issuer}/.well-known/jwks.json' if issuer else ''


def auth_is_configured():
    return bool(get_issuer())


# Un client JWKS par URL : il met les clés en cache (inutile de les retélécharger).
_jwk_clients = {}


def _get_jwk_client(jwks_url):
    client = _jwk_clients.get(jwks_url)
    if client is None:
        client = jwt.PyJWKClient(jwks_url)
        _jwk_clients[jwks_url] = client
    return client


def verify_clerk_token(token):
    """Vérifie le jeton et retourne l'identifiant utilisateur (``sub``).

    Lève ``AuthNotConfigured`` si Clerk n'est pas configuré et ``InvalidToken``
    pour tout jeton refusé (signature, expiration, émetteur, ``azp``…).
    """
    issuer = get_issuer()
    if not issuer:
        raise AuthNotConfigured()

    try:
        signing_key = _get_jwk_client(get_jwks_url()).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256'],
            issuer=issuer,
            options={'require': ['exp', 'sub'], 'verify_aud': False},
            leeway=CLOCK_LEEWAY_SECONDS,
        )
    except jwt.PyJWTError as exc:
        # Inclut les erreurs de téléchargement des clés (PyJWKClientError).
        raise InvalidToken() from exc

    user_id = claims.get('sub')
    if not isinstance(user_id, str) or not user_id:
        raise InvalidToken()

    authorized_parties = getattr(settings, 'CLERK_AUTHORIZED_PARTIES', None) or []
    azp = claims.get('azp')
    if authorized_parties and azp is not None:
        if not isinstance(azp, str) or azp.rstrip('/') not in authorized_parties:
            raise InvalidToken()

    return user_id


def extract_bearer_token(request):
    """Jeton de l'en-tête ``Authorization: Bearer …`` (chaîne vide si absent)."""
    header = request.META.get('HTTP_AUTHORIZATION', '')
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'bearer':
        return ''
    return token.strip()


def clerk_auth_required(view):
    """Réserve une vue aux utilisateurs Clerk connectés ; pose ``request.clerk_user_id``.

    Répond en JSON : 503 si Clerk n'est pas configuré, 401 si le jeton est
    absent ou refusé. Les vues sont exemptées de CSRF (jeton, pas de cookie).
    """

    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not auth_is_configured():
            return json_error('auth_not_configured', 503)

        token = extract_bearer_token(request)
        if not token:
            return json_error('authentication_required', 401)

        try:
            request.clerk_user_id = verify_clerk_token(token)
        except AuthNotConfigured:
            return json_error('auth_not_configured', 503)
        except InvalidToken:
            return json_error('authentication_required', 401)

        # Dernière activité de l'usager (page « Mail » de l'administration).
        from .models import EspaceVisitor

        EspaceVisitor.record(request.clerk_user_id)
        return view(request, *args, **kwargs)

    return wrapper
