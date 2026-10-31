"""
Assistant IA (local, sans service externe) des espaces agent et administration.

Il comprend des phrases simples par mots-clés et ne travaille que sur les données de
l'application que l'utilisateur a le droit de voir : un agent, les demandes de son guichet ;
l'administrateur, toutes. Il répond aux questions (statistiques, file d'attente, recherche
d'une demande) et prépare des actions (prendre en charge, approuver, refuser, terminer,
répondre à l'usager) qui ne s'exécutent qu'après confirmation, avec les mêmes contrôles
que les pages (premier arrivé, premier servi pour les agents). Tout le reste : « je ne
peux pas ».
"""
import datetime
import re
import unicodedata
from dataclasses import dataclass, field

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from espace.models import DossierRequest

from .access import agent_profile
from .forms import DecisionForm
from .guichets import GUICHETS, guichet_for_type
from .official import OFFICIAL_DOCUMENTS
from .queue import blocked_message, blocking_request

Status = DossierRequest.Status

# Mots-clés (sans accents, en minuscules) : français, quelques mots anglais et malgaches.
HELP_WORDS = ('aide', 'help', 'que peux', 'que sais', 'quoi faire', 'comment', 'bonjour', 'salut', 'fanampiana', 'manao ahoana')
STATS_WORDS = ('combien', 'nombre', 'statist', 'bilan', 'resume', 'how many', 'firy')
REQUEST_WORDS = ('a ma place', 'peux', 'pourrais', 'stp', 'svp', 'merci de', 'please')
QUESTION_WORDS = ('quelle', 'quel', 'laquelle', 'lequel', 'qui est', 'which', 'what')
QUEUE_WORDS = ('prochaine', 'suivante', 'premiere', 'plus ancienne', 'a traiter', 'file', 'next', 'manaraka')
SEARCH_WORDS = ('cherche', 'trouve', 'montre', 'affiche', 'info', 'detail', 'statut de', 'ou en est', 'find', 'show')
LIST_WORDS = ('dernieres', 'recentes', 'liste', 'toutes les demandes', 'latest')
DOCUMENT_WORDS = ('etabli', 'etablir', 'cree', 'creer', 'genere', 'rediger', 'redige', 'prepare')
DOCUMENT_NOUNS = ('acte', 'document', 'attestation', 'extrait', 'certificat', 'pdf')
SECURITY_WORDS = ('fraude', 'altere', 'securite', 'falsifi', 'fraud')
ACCESS_WORDS = ("demandes d'acces", 'demande d acces', 'acces agent', 'nouveaux agents', 'inscription')
CONTACT_WORDS = ('message de contact', 'messages de contact', 'contact')
THIS_WORDS = ('cette demande', 'celle-ci', 'celle ci', 'ce dossier', 'cette', 'ici', 'this')
ACTIONS = (
    # (statut visé, mots-clés) : le premier qui correspond l'emporte.
    (Status.REJECTED, ('refuse', 'rejette', 'rejeter', 'reject', 'decline')),
    (Status.APPROVED, ('approuve', 'accepte', 'valide', 'approve', 'accept')),
    (Status.COMPLETED, ('termine', 'cloture', 'clos', 'finis', 'acheve', 'complete')),
    (Status.IN_PROGRESS, ('prends en charge', 'prendre en charge', 'prise en charge', 'commence', 'traite',
                          'traiter', 'occupe', 'fais', 'faire', 'a ma place', 'process', 'start')),
)
REPLY_WORDS = ('reponds', 'repondre', 'reponse', 'ecris', 'message a', 'dis lui', 'dis-lui', 'reply')
REFERENCE_RE = re.compile(r'\bmv[\s-]?(\d{4})[\s-]?(\d{1,6})\b', re.IGNORECASE)
PAGE_RE = re.compile(r'/(?:demandes|dossierrequest)/(\d+)/')
NAME_STOPWORDS = {
    'demande', 'demandes', 'dossier', 'client', 'cliente', 'usager', 'usagere', 'monsieur', 'madame',
    'mademoiselle', 'acte', 'mariage', 'naissance', 'deces', 'place', 'pour', 'avec', 'cette', 'celle',
    'prochaine', 'suivante', 'premiere', 'motif', 'parce', 'merci', 'stp', 'svp', 'peux', 'peut', 'faire',
    'traite', 'traiter', 'approuve', 'refuse', 'termine', 'valide', 'accepte', 'charge', 'prends', 'reponds',
    'request', 'requests', 'the', 'this', 'next', 'please',
}


def normalize(text):
    text = unicodedata.normalize('NFD', text or '').encode('ascii', 'ignore').decode()
    return ' '.join(text.lower().replace('’', "'").split())


def _has(text, words):
    """Un des mots-clés commence un mot de la phrase (« refuse » trouve « refusée », pas « recette » → « cette »)."""
    return any(re.search(r'(?<![a-z])' + re.escape(word), text) for word in words)


def _applicant(dossier):
    identity = dossier.identity or {}
    return f"{identity.get('last_name', '')} {identity.get('first_name', '')}".strip() or '—'


def _when(value):
    return date_format(timezone.localtime(value), 'DATETIME_FORMAT')


@dataclass
class Reply:
    text: str
    items: list = field(default_factory=list)
    confirm: dict | None = None

    def as_json(self):
        return {'text': self.text, 'items': self.items, 'confirm': self.confirm}


@dataclass
class Scope:
    """Ce que l'utilisateur peut voir et faire."""
    user: object
    guichet: int | None  # None : administrateur (tous les guichets)
    types: tuple

    @property
    def is_admin(self):
        return self.guichet is None

    def requests(self):
        return DossierRequest.objects.filter(dossier_type__in=self.types)

    def can_change(self):
        return not self.is_admin or self.user.has_perm('espace.change_dossierrequest')

    def request_url(self, dossier):
        if self.is_admin:
            return reverse('admin:espace_dossierrequest_change', args=[dossier.pk])
        return reverse('agents:request_detail', args=[self.guichet, dossier.pk])

    def item(self, dossier):
        return {
            'label': f'{dossier.reference or dossier.pk} — {dossier.get_dossier_type_display()}',
            'meta': f'{_applicant(dossier)} · {dossier.get_status_display()} · {_when(dossier.created_at)}',
            'url': self.request_url(dossier),
        }


def scope_for(user):
    """Périmètre de l'assistant pour ce compte, ou None (pas d'accès)."""
    profile = agent_profile(user)
    if profile is not None:
        return Scope(user, profile.guichet, tuple(GUICHETS[profile.guichet].dossier_types))
    if user.is_staff and user.has_perm('espace.view_dossierrequest'):
        return Scope(user, None, tuple(DossierRequest.DossierType.values))
    return None


# -- Réponses -------------------------------------------------------------------

def _help(scope):
    lines = [
        _("Je suis l'assistant de l'application. Je ne connais que les demandes et documents de %(where)s. Exemples :")
        % {'where': _('votre guichet') if not scope.is_admin else _('tous les guichets')},
        _('• « Quelle est la prochaine demande à traiter ? »'),
        _('• « Combien de demandes en attente ? »'),
        _('• « Montre la demande MV-2026-000012 » ou « la demande de Rabe »'),
        _('• « Prends en charge la prochaine demande à ma place »'),
        _('• « Approuve cette demande : votre acte est prêt » / « Refuse la demande de Rabe motif : pièce manquante »'),
    ]
    if scope.is_admin or scope.guichet in OFFICIAL_DOCUMENTS:
        lines.append(_("• « Établis l'acte de la prochaine demande »"))
    if scope.is_admin:
        lines.append(_('• « Y a-t-il des fraudes ? » · « Demandes d\'accès agent en attente ? »'))
    return Reply('\n'.join(lines))


def _out_of_scope():
    return Reply(_(
        "Je ne peux pas vous aider pour cela : je réponds seulement aux questions sur l'application "
        "(demandes, documents, guichets) et j'effectue les tâches de cette page. Tapez « aide » pour des exemples."
    ))


def _stats(scope):
    requests = scope.requests()
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - datetime.timedelta(days=today.weekday())
    counts = {status: requests.filter(status=status).count() for status in Status.values}
    lines = [
        _('Demandes : %(total)s au total — %(new_today)s aujourd\'hui, %(new_week)s cette semaine.') % {
            'total': requests.count(),
            'new_today': requests.filter(created_at__gte=today).count(),
            'new_week': requests.filter(created_at__gte=week).count(),
        },
        ' · '.join(f'{label} : {counts[value]}' for value, label in Status.choices),
    ]
    numbers = [scope.guichet] if scope.guichet else list(OFFICIAL_DOCUMENTS)
    issued = sum(
        OFFICIAL_DOCUMENTS[n].model.objects.filter(deleted_at=None).count()
        for n in numbers if n in OFFICIAL_DOCUMENTS
    )
    lines.append(_('Documents officiels établis : %(count)s.') % {'count': issued})
    if scope.is_admin:
        by_type = [
            f'{label} : {requests.filter(dossier_type=value).count()}'
            for value, label in DossierRequest.DossierType.choices
            if requests.filter(dossier_type=value).exists()
        ]
        if by_type:
            lines.append(_('Par type : %(list)s.') % {'list': ', '.join(by_type)})
    return Reply('\n'.join(lines))


def _queue_heads(scope):
    """Demande la plus ancienne en attente, pour chaque type du périmètre."""
    heads = []
    for dossier_type in scope.types:
        head = (
            scope.requests().filter(dossier_type=dossier_type, status=Status.PENDING)
            .order_by('created_at', 'pk').first()
        )
        if head is not None:
            heads.append(head)
    return sorted(heads, key=lambda dossier: (dossier.created_at, dossier.pk))


def _queue(scope):
    heads = _queue_heads(scope)
    if not heads:
        return Reply(_('Aucune demande en attente : tout est à jour.'))
    waiting = scope.requests().filter(status=Status.PENDING).count()
    return Reply(
        _('%(count)s demande(s) en attente. À traiter en premier (ordre d\'arrivée) :') % {'count': waiting},
        [scope.item(dossier) for dossier in heads],
    )


def _latest(scope):
    latest = list(scope.requests().order_by('-created_at')[:5])
    if not latest:
        return Reply(_('Aucune demande pour le moment.'))
    return Reply(_('Les dernières demandes reçues :'), [scope.item(dossier) for dossier in latest])


def _security(scope):
    from core import security

    if not scope.user.has_perm('documents.view_documentauditlog'):
        return _out_of_scope()
    rows = security.analyse_documents()
    altered = [row for row in rows if row['level'] == security.ALTERED]
    deletions = [row for row in rows if row['level'] == security.DELETION]
    text = _('%(total)s document(s) contrôlé(s) : %(altered)s altéré(s), %(deletions)s suppression(s) demandée(s).') % {
        'total': len(rows), 'altered': len(altered), 'deletions': len(deletions),
    }
    items = [
        {'label': row['number'], 'meta': f"{row['kind']} · {row['level_label']}", 'url': row['admin_url']}
        for row in altered + deletions
    ][:8]
    items.append({'label': _('Ouvrir « Sécurité et fraude »'), 'meta': '', 'url': reverse('admin:security')})
    return Reply(text, items)


def _access_requests(scope):
    from documents.models import AgentAccessRequest

    if not scope.user.has_perm('documents.view_agentaccessrequest'):
        return _out_of_scope()
    pending = AgentAccessRequest.objects.filter(status=AgentAccessRequest.Status.PENDING)
    return Reply(
        _("%(count)s demande(s) d'accès agent en attente de votre validation.") % {'count': pending.count()},
        [{'label': _("Ouvrir les demandes d'accès agent"), 'meta': '',
          'url': reverse('admin:documents_agentaccessrequest_changelist') + '?status__exact=PENDING'}],
    )


def _contact_messages(scope):
    from espace.models import ContactMessage

    if not scope.user.has_perm('espace.view_contactmessage'):
        return _out_of_scope()
    count = ContactMessage.objects.filter(handled=False).count()
    return Reply(
        _('%(count)s message(s) de contact non traité(s).') % {'count': count},
        [{'label': _('Ouvrir les messages de contact'), 'meta': '',
          'url': reverse('admin:espace_contactmessage_changelist') + '?handled__exact=0'}],
    )


# -- Trouver la demande visée ---------------------------------------------------------

def _name_words(text):
    """Mots qui ressemblent à un nom de personne dans la phrase (après « de », « pour »…)."""
    match = re.search(r"\b(?:de|du|pour|for|of|client|cliente|usager|monsieur|madame|mme|mr|m\.)\s+(.+)", text)
    if not match:
        return []
    tail = re.split(r'[:,.;!?]| motif| car | parce| reason', match.group(1))[0]
    return [word for word in re.findall(r"[a-z'-]{3,}", tail) if word not in NAME_STOPWORDS][:3]


def _find_targets(scope, text, page_pk):
    """Demandes visées par la phrase : référence, « cette demande », « la prochaine », ou nom de l'usager."""
    match = REFERENCE_RE.search(text)
    if match:
        reference = f'MV-{match.group(1)}-{int(match.group(2)):06d}'
        return list(scope.requests().filter(reference__iexact=reference))
    if page_pk and _has(text, THIS_WORDS):
        return list(scope.requests().filter(pk=page_pk))
    if _has(text, QUEUE_WORDS):
        heads = _queue_heads(scope)
        return heads[:1]
    words = _name_words(text)
    if words:
        query = Q()
        for word in words:
            query |= Q(identity__last_name__icontains=word) | Q(identity__first_name__icontains=word)
        found = list(scope.requests().filter(query).order_by('status', 'created_at')[:6])
        if found:
            return found
    if page_pk:
        return list(scope.requests().filter(pk=page_pk))
    return []


def _ask_which(scope, found):
    if not found:
        return Reply(_(
            'Je ne trouve pas la demande. Donnez sa référence (ex. MV-2026-000012), le nom de l\'usager, '
            'ou dites « la prochaine demande ».'
        ))
    return Reply(
        _('Plusieurs demandes correspondent. Précisez la référence :'),
        [scope.item(dossier) for dossier in found],
    )


def _reply_text(original):
    """Message pour l'usager : ce qui suit « : » ou « motif » dans la phrase (casse d'origine)."""
    match = re.search(r'(?:\s:\s*|:\s|motif\s*:?\s*|reason\s*:?\s*|car\s+|parce que\s+)(.+)$', original, re.IGNORECASE)
    return match.group(1).strip()[:4000] if match else ''


# -- Actions ----------------------------------------------------------------------------

def _queue_check(scope, dossier):
    """Message de blocage (premier arrivé, premier servi) pour un agent, sinon None."""
    if scope.is_admin:
        return None
    blocker = blocking_request(dossier)
    return blocked_message(blocker) if blocker else None


def _propose_status(scope, text, original, page_pk, status):
    if not scope.can_change():
        return Reply(_("Votre compte ne permet pas de modifier les demandes."))
    found = _find_targets(scope, text, page_pk)
    if len(found) != 1:
        return _ask_which(scope, found)
    dossier = found[0]
    blocked = _queue_check(scope, dossier)
    if blocked:
        return Reply(blocked, [scope.item(blocking_request(dossier))])
    message = _reply_text(original)
    summary = _('Je vais passer la demande %(reference)s (%(person)s) au statut « %(status)s ».') % {
        'reference': dossier.reference, 'person': _applicant(dossier), 'status': Status(status).label,
    }
    if message:
        summary += '\n' + _('Message envoyé à l\'usager : « %(message)s »') % {'message': message}
    elif status == Status.REJECTED:
        summary += '\n' + _('Astuce : ajoutez « motif : … » pour expliquer le refus à l\'usager.')
    return Reply(
        summary + '\n' + _('Confirmez-vous ?'),
        [scope.item(dossier)],
        confirm={'action': 'status', 'pk': dossier.pk, 'status': status, 'message': message},
    )


def _propose_reply(scope, text, original, page_pk):
    message = _reply_text(original)
    if not message:
        return Reply(_('Écrivez le message après deux-points, ex. « Réponds à cette demande : votre dossier est prêt »'))
    if not scope.can_change():
        return Reply(_("Votre compte ne permet pas de modifier les demandes."))
    found = _find_targets(scope, text, page_pk)
    if len(found) != 1:
        return _ask_which(scope, found)
    dossier = found[0]
    blocked = _queue_check(scope, dossier)
    if blocked:
        return Reply(blocked, [scope.item(blocking_request(dossier))])
    return Reply(
        _('Je vais envoyer ce message à %(person)s (demande %(reference)s) : « %(message)s ». Confirmez-vous ?') % {
            'person': _applicant(dossier), 'reference': dossier.reference, 'message': message,
        },
        [scope.item(dossier)],
        confirm={'action': 'status', 'pk': dossier.pk, 'status': dossier.status, 'message': message},
    )


def _document(scope, text, page_pk):
    found = _find_targets(scope, text, page_pk)
    if len(found) != 1:
        return _ask_which(scope, found)
    dossier = found[0]
    number = guichet_for_type(dossier.dossier_type)
    if number not in OFFICIAL_DOCUMENTS:
        return Reply(_("Ce guichet n'établit pas de documents officiels."))
    blocked = _queue_check(scope, dossier)
    if blocked:
        return Reply(blocked, [scope.item(blocking_request(dossier))])
    spec = OFFICIAL_DOCUMENTS[number]
    url = reverse('agents:document_create', args=[number]) + f'?demande={dossier.pk}'
    return Reply(
        _("Le formulaire est pré-rempli avec les informations de la demande %(reference)s : "
          "vérifiez-le, complétez-le puis enregistrez pour sceller le document.") % {'reference': dossier.reference},
        [{'label': str(spec.issue_label), 'meta': _applicant(dossier), 'url': url}],
    )


def _search(scope, text, page_pk):
    found = _find_targets(scope, text, page_pk)
    if not found:
        return _ask_which(scope, found)
    if len(found) > 1:
        return Reply(_('Demandes trouvées :'), [scope.item(dossier) for dossier in found])
    dossier = found[0]
    lines = [
        _('Demande %(reference)s — %(type)s, déposée le %(date)s par %(person)s.') % {
            'reference': dossier.reference, 'type': dossier.get_dossier_type_display(),
            'date': _when(dossier.created_at), 'person': _applicant(dossier),
        },
        _('Statut : %(status)s.') % {'status': dossier.get_status_display()},
    ]
    blocker = blocking_request(dossier)
    if dossier.status == Status.PENDING:
        lines.append(
            _('À traiter après %(reference)s (ordre d\'arrivée).') % {'reference': blocker.reference}
            if blocker else _('C\'est la prochaine demande de ce type à traiter.')
        )
    if dossier.response_message:
        lines.append(_('Réponse déjà envoyée : « %(message)s »') % {'message': dossier.response_message[:200]})
    return Reply('\n'.join(lines), [scope.item(dossier)])


def answer(user, message, page=''):
    """Réponse de l'assistant à une phrase de l'utilisateur."""
    scope = scope_for(user)
    if scope is None:
        return Reply(_("L'assistant est réservé aux agents et aux administrateurs."))
    original = (message or '').strip()[:1000]
    text = normalize(original)
    page_match = PAGE_RE.search(page or '')
    page_pk = int(page_match.group(1)) if page_match else None

    # « Bonjour » seul ou « aide » : exemples ; « Bonjour, approuve… » : on traite la demande.
    other_words = (STATS_WORDS + QUEUE_WORDS + SEARCH_WORDS + DOCUMENT_WORDS + SECURITY_WORDS + REPLY_WORDS
                   + tuple(word for _status, words in ACTIONS for word in words))
    if not text or text.startswith('comment') or (_has(text, HELP_WORDS) and not _has(text, other_words) and not REFERENCE_RE.search(text)):
        return _help(scope)
    if scope.is_admin and _has(text, SECURITY_WORDS):
        return _security(scope)
    if scope.is_admin and _has(text, ACCESS_WORDS):
        return _access_requests(scope)
    if scope.is_admin and _has(text, CONTACT_WORDS) and not REFERENCE_RE.search(text):
        return _contact_messages(scope)
    if _has(text, STATS_WORDS):
        return _stats(scope)
    asks = _has(text, QUESTION_WORDS) or text.endswith('?')
    if _has(text, QUEUE_WORDS) and asks and not _has(text, REQUEST_WORDS) and not REFERENCE_RE.search(text):
        return _queue(scope)
    if _has(text, DOCUMENT_WORDS) and _has(text, DOCUMENT_NOUNS):
        return _document(scope, text, page_pk)
    for status, words in ACTIONS:
        if _has(text, words):
            return _propose_status(scope, text, original, page_pk, status)
    if _has(text, REPLY_WORDS):
        return _propose_reply(scope, text, original, page_pk)
    if REFERENCE_RE.search(text) or _has(text, SEARCH_WORDS) or _name_words(text):
        return _search(scope, text, page_pk)
    if _has(text, QUEUE_WORDS) or 'en attente' in text:
        return _queue(scope)
    if _has(text, LIST_WORDS):
        return _latest(scope)
    return _out_of_scope()


def confirm(user, payload):
    """Exécute une action proposée, après confirmation, avec les contrôles habituels."""
    scope = scope_for(user)
    if scope is None or not isinstance(payload, dict) or payload.get('action') != 'status':
        return Reply(_('Action inconnue.'))
    if not scope.can_change():
        return Reply(_("Votre compte ne permet pas de modifier les demandes."))
    dossier = scope.requests().filter(pk=payload.get('pk')).first()
    if dossier is None:
        return Reply(_('Je ne trouve pas la demande.'))
    blocked = _queue_check(scope, dossier)
    if blocked:
        return Reply(blocked)
    message = str(payload.get('message') or '')[:4000]
    form = DecisionForm(
        {'status': payload.get('status'), 'response_message': message or dossier.response_message},
        instance=dossier,
    )
    if not form.is_valid():
        return Reply(_('Action impossible : %(errors)s') % {'errors': ' '.join(form.errors.get('status', []))})
    form.save()
    return Reply(
        _('C\'est fait : la demande %(reference)s est maintenant « %(status)s ».') % {
            'reference': dossier.reference, 'status': dossier.get_status_display(),
        },
        [scope.item(dossier)],
    )
