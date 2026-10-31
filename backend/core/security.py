"""
« Sécurité et fraude » : contrôle des documents officiels établis par les agents.

Chaque document est re-vérifié à l'ouverture de la page : on recalcule son empreinte
SHA-256 et sa signature HMAC et on les compare à celles enregistrées lors du scellement.
Une différence signifie que le contenu a été modifié après coup (en base de données,
hors de l'application) : c'est une alerte de fraude.
"""
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _

from agents.official import OFFICIAL_DOCUMENTS

# Niveaux d'alerte, du plus grave au moins grave (ordre d'affichage).
ALTERED = 'altered'
DELETION = 'deletion'
REVOKED = 'revoked'
OK = 'ok'
LEVEL_ORDER = {ALTERED: 0, DELETION: 1, REVOKED: 2, OK: 3}
LEVEL_LABELS = {
    ALTERED: _('Altéré — fraude'),
    DELETION: _('Suppression demandée'),
    REVOKED: _('Révoqué / supprimé'),
    OK: _('Intègre'),
}


def _person(user):
    if user is None:
        return ''
    return user.get_full_name() or user.get_username()


def _admin_url(act, site_name):
    meta = act._meta
    try:
        return reverse(f'{site_name}:{meta.app_label}_{meta.model_name}_change', args=[act.pk])
    except NoReverseMatch:
        return ''


def analyse_documents(site_name='admin'):
    """Tous les documents des guichets, re-vérifiés, les plus graves en premier."""
    rows = []
    for spec in OFFICIAL_DOCUMENTS.values():
        queryset = spec.model.objects.select_related('created_by', 'deletion_requested_by')
        for act in queryset:
            result = act.verify()
            intact = result['hash_matches'] and result['signature_valid']
            if not intact:
                level = ALTERED
            elif act.deletion_pending:
                level = DELETION
            elif result['status'] == 'REVOKED':
                level = REVOKED
            else:
                level = OK
            rows.append({
                'act': act,
                'kind': act._meta.verbose_name,
                'guichet': spec.guichet,
                'number': act.act_number,
                'holder': act.holder_name,
                'agent': _person(act.created_by),
                'agent_id': act.created_by_id,
                'created_at': act.created_at,
                'hash_matches': result['hash_matches'],
                'signature_valid': result['signature_valid'],
                'level': level,
                'level_label': LEVEL_LABELS[level],
                'deletion_reason': act.deletion_reason if act.deletion_pending else '',
                'deletion_by': _person(act.deletion_requested_by) if act.deletion_pending else '',
                'sent': act.sent_at is not None,
                'admin_url': _admin_url(act, site_name),
            })
    rows.sort(key=lambda row: (LEVEL_ORDER[row['level']], -row['created_at'].timestamp()))
    return rows


def agents_summary(rows):
    """Par agent : documents établis, documents altérés, suppressions demandées."""
    agents = {}
    for row in rows:
        key = row['agent_id']
        entry = agents.setdefault(key, {
            'name': row['agent'] or _('Agent inconnu'),
            'guichets': set(),
            'documents': 0,
            'altered': 0,
            'deletions': 0,
            'last': None,
        })
        entry['guichets'].add(row['guichet'])
        entry['documents'] += 1
        entry['altered'] += row['level'] == ALTERED
        entry['deletions'] += row['level'] == DELETION
        if entry['last'] is None or row['created_at'] > entry['last']:
            entry['last'] = row['created_at']
    summary = []
    for entry in agents.values():
        entry['guichets'] = ', '.join(str(number) for number in sorted(entry['guichets']))
        summary.append(entry)
    summary.sort(key=lambda entry: (-entry['altered'], -entry['deletions'], -entry['documents']))
    return summary
