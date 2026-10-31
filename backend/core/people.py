"""Personnes qui utilisent l'application : équipe (comptes Django) et usagers (comptes Clerk de l'espace)."""
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _

# Un usager est « en ligne » s'il a utilisé l'espace dans ce délai.
ONLINE_WINDOW_MINUTES = 5


def _team_sessions():
    """Identifiants des comptes ayant une session ouverte (non expirée)."""
    ids = set()
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        user_id = session.get_decoded().get('_auth_user_id')
        if user_id:
            ids.add(str(user_id))
    return ids


def _role(user):
    if user.is_superuser:
        return _('Administrateur principal')
    if user.is_staff:
        return _('Administrateur')
    profile = getattr(user, 'agent_profile', None)
    if profile is not None:
        return _('Agent — Guichet %(number)s') % {'number': profile.guichet}
    return _('Compte sans rôle')


def collect():
    """Liste triée (en ligne d'abord, puis activité la plus récente) de toutes les personnes."""
    from espace.models import DossierRequest, EspaceVisitor

    now = timezone.now()
    online_since = now - timezone.timedelta(minutes=ONLINE_WINDOW_MINUTES)
    people = []

    # Équipe : administrateurs et agents.
    open_sessions = _team_sessions()
    for user in get_user_model().objects.select_related('agent_profile'):
        people.append({
            'kind': 'team',
            'name': user.get_full_name() or user.get_username(),
            'email': user.email,
            'phone': '',
            'role': _role(user),
            'active': user.is_active,
            'last_seen': user.last_login,
            'online': user.is_active and str(user.pk) in open_sessions,
            'requests': None,
            'admin_url': reverse('admin:auth_user_change', args=[user.pk]),
        })

    # Usagers : identité tirée de leur demande la plus récente.
    latest_identity = {}
    counts = {}
    for clerk_id, identity, created in (
        DossierRequest.objects.order_by('created_at').values_list('clerk_user_id', 'identity', 'created_at')
    ):
        latest_identity[clerk_id] = (identity or {}, created)
        counts[clerk_id] = counts.get(clerk_id, 0) + 1

    seen = {visitor.clerk_user_id: visitor.last_seen for visitor in EspaceVisitor.objects.all()}
    for clerk_id in set(seen) | set(latest_identity):
        identity, last_request = latest_identity.get(clerk_id, ({}, None))
        last_seen = seen.get(clerk_id) or last_request
        name = f"{identity.get('first_name', '')} {identity.get('last_name', '')}".strip()
        people.append({
            'kind': 'citizen',
            'name': name or _('Usager (pas encore de demande)'),
            'email': identity.get('email', ''),
            'phone': identity.get('phone', ''),
            'role': _('Usager'),
            'active': True,
            'last_seen': last_seen,
            'online': bool(seen.get(clerk_id) and seen[clerk_id] >= online_since),
            'requests': counts.get(clerk_id, 0),
            'admin_url': (
                f"{reverse('admin:espace_dossierrequest_changelist')}?{urlencode({'q': clerk_id})}"
                if counts.get(clerk_id) else ''
            ),
        })

    epoch = timezone.make_aware(timezone.datetime(1970, 1, 1))
    people.sort(key=lambda p: (not p['online'], -(p['last_seen'] or epoch).timestamp()))
    return people
