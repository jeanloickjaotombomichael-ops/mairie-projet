"""Création du compte d'un agent quand l'administrateur approuve sa demande d'accès."""
import re
import secrets
import unicodedata

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import AgentProfile


def _slug(text):
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '.', text.lower()).strip('.')


def unique_username(first_name, last_name):
    """prenom.nom, suivi d'un numéro si ce nom d'utilisateur est déjà pris."""
    User = get_user_model()
    base = '.'.join(part for part in (_slug(first_name), _slug(last_name)) if part) or 'agent'
    base = base[:140]
    username, n = base, 2
    while User.objects.filter(username__iexact=username).exists():
        username, n = f'{base}{n}', n + 1
    return username


@transaction.atomic
def create_agent_account(access_request):
    """
    Crée le compte (sans accès à l'administration) et le rôle de guichet.

    Si l'agent a choisi son mot de passe à l'inscription, son e-mail devient
    son identifiant et le mot de passe (haché) est repris tel quel : la
    fonction renvoie alors (utilisateur, None). Sinon (demande envoyée depuis
    le site public), un mot de passe provisoire est généré et renvoyé pour
    être transmis à l'agent.
    """
    User = get_user_model()
    email = access_request.email.strip().lower()
    chosen = bool(access_request.password_hash)
    if chosen and not User.objects.filter(username__iexact=email).exists():
        username = email
    else:
        username = unique_username(access_request.first_name, access_request.last_name)

    user = User(
        username=username,
        email=email,
        first_name=access_request.first_name,
        last_name=access_request.last_name,
        is_staff=False,
    )
    password = None
    if chosen:
        user.password = access_request.password_hash
    else:
        password = secrets.token_urlsafe(9)
        user.set_password(password)
    user.save()
    AgentProfile.objects.create(user=user, guichet=access_request.guichet)
    return user, password
