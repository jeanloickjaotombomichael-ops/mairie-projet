"""Vues JSON de l'espace usager : demandes de dossiers, réponses et contact.

Les dossiers exigent un jeton de session Clerk (voir ``auth.py``) ; le contact
est public. Les erreurs de validation ont la forme
``{"errors": {"<champ>": ["<code>", ...]}}`` avec les codes ``required``,
``invalid`` et ``too_long``.
"""
import json
import re

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from documents.views import get_client_ip, json_error

from .auth import clerk_auth_required
from .models import ContactMessage, DossierRequest
from .ratelimit import is_rate_limited
from .schemas import CONTACT_FIELDS, IDENTITY_FIELDS, INVALID, REQUIRED, clean_fields, detail_specs

GUICHET_PATTERN = re.compile(r'^[1-5]-[A-E]$')
MAX_LIST_RESULTS = 200


def _read_json_object(request):
    """Corps JSON de la requête s'il s'agit d'un objet, sinon None."""
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _invalid_json_response():
    return JsonResponse({'errors': {'__all__': ['invalid_json']}}, status=400)


def _iso(value):
    return value.isoformat() if value else None


def _documents(dossier, documents=None):
    """Documents envoyés à l'usager pour cette demande (téléchargeables depuis ses notifications)."""
    if documents is None:
        from agents.official import documents_for_request

        documents = documents_for_request(dossier)
    return [
        {
            'id': str(act.id),
            'label': f'Bon de retrait — {act.label}',
            'filename': act.ticket_filename,
            'sent_at': _iso(act.sent_at),
        }
        for act in documents
        if act.downloadable_by_requester
    ]


def serialize_dossier(dossier, documents=None):
    return {
        'id': dossier.id,
        'reference': dossier.reference or '',
        'dossier_type': dossier.dossier_type,
        'guichet': dossier.guichet,
        'status': dossier.status,
        'created_at': _iso(dossier.created_at),
        'updated_at': _iso(dossier.updated_at),
        'response_message': dossier.response_message or '',
        'responded_at': _iso(dossier.responded_at),
        'response_read': dossier.response_read,
        'documents': _documents(dossier, documents),
    }


# ----------------------------------------------------------------------
# Dossiers (authentifiés)
# ----------------------------------------------------------------------
@clerk_auth_required
@require_http_methods(['GET', 'POST'])
def dossier_collection(request):
    """GET : liste des dossiers de l'utilisateur ; POST : dépôt d'une demande."""
    if request.method == 'GET':
        return _list_dossiers(request)
    return _create_dossier(request)


def _list_dossiers(request):
    from agents.official import documents_for_requests

    dossiers = list(DossierRequest.objects.filter(clerk_user_id=request.clerk_user_id)[:MAX_LIST_RESULTS])
    documents = documents_for_requests(dossier.pk for dossier in dossiers)
    return JsonResponse({
        'results': [serialize_dossier(dossier, documents.get(dossier.pk, [])) for dossier in dossiers],
    })


def _create_dossier(request):
    limit, window = getattr(settings, 'DOSSIER_RATE_LIMIT', (30, 3600))
    if is_rate_limited(f'dossier-rate:{request.clerk_user_id}', limit, window):
        return json_error('throttled', 429)

    data = _read_json_object(request)
    if data is None:
        return _invalid_json_response()

    errors = {}

    # Type de dossier.
    dossier_type = data.get('dossier_type')
    specs = detail_specs(dossier_type) if isinstance(dossier_type, str) else None
    if specs is None:
        errors['dossier_type'] = [INVALID if dossier_type not in (None, '') else REQUIRED]

    # Guichet (facultatif) : « 1-A » … « 5-E ».
    guichet = data.get('guichet')
    if guichet is None:
        guichet = ''
    if not isinstance(guichet, str):
        errors['guichet'] = [INVALID]
        guichet = ''
    guichet = guichet.strip()
    if guichet and not GUICHET_PATTERN.match(guichet):
        errors['guichet'] = [INVALID]

    # Identité et détails (un bloc absent ou mal formé est traité comme vide).
    identity, identity_errors = clean_fields(IDENTITY_FIELDS, data.get('identity'), 'identity')
    errors.update(identity_errors)

    details = {}
    if specs is not None:
        details, details_errors = clean_fields(specs, data.get('details'), 'details')
        errors.update(details_errors)

    if errors:
        return JsonResponse({'errors': errors}, status=400)

    dossier = DossierRequest.objects.create(
        clerk_user_id=request.clerk_user_id,
        dossier_type=dossier_type,
        guichet=guichet,
        identity=identity,
        details=details,
    )
    return JsonResponse(
        {
            'id': dossier.id,
            'reference': dossier.reference,
            'status': dossier.status,
            'created_at': _iso(dossier.created_at),
        },
        status=201,
    )


@clerk_auth_required
@require_POST
def dossier_mark_read(request, pk):
    """Marque la réponse d'un dossier comme lue (404 si ce n'est pas le sien)."""
    dossiers = DossierRequest.objects.filter(pk=pk, clerk_user_id=request.clerk_user_id)
    if not dossiers.exists():
        return json_error('not_found', 404)
    dossiers.update(response_read=True)
    return JsonResponse({'ok': True})


@clerk_auth_required
@require_POST
def dossier_read_all(request):
    """Marque toutes les réponses non lues de l'utilisateur comme lues."""
    unread = (
        DossierRequest.objects.filter(clerk_user_id=request.clerk_user_id, response_read=False)
        .exclude(response_message='')
    )
    updated = unread.update(response_read=True)
    return JsonResponse({'updated': updated})


# ----------------------------------------------------------------------
# Contact (public)
# ----------------------------------------------------------------------
@clerk_auth_required
@require_GET
def dossier_document(request, pk, document_id):
    """Bon de retrait envoyé à l'usager : uniquement le sien, pour sa propre demande."""
    from agents.official import find_document
    from agents.pdf import ticket_pdf

    act = find_document(document_id)
    if (
        act is None or act.request_id != pk or act.request.clerk_user_id != request.clerk_user_id
        or not act.downloadable_by_requester
    ):
        return json_error('not_found', 404)

    response = HttpResponse(ticket_pdf(act), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{act.ticket_filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@csrf_exempt  # endpoint public, sans session ni cookie : le CSRF ne s'applique pas
@require_POST
def contact_create(request):
    limit, window = getattr(settings, 'CONTACT_RATE_LIMIT', (10, 3600))
    if is_rate_limited(f"contact-rate:{get_client_ip(request) or 'unknown'}", limit, window):
        return json_error('throttled', 429)

    data = _read_json_object(request)
    if data is None:
        return _invalid_json_response()

    cleaned, errors = clean_fields(CONTACT_FIELDS, data)
    if errors:
        return JsonResponse({'errors': errors}, status=400)

    message = ContactMessage.objects.create(**cleaned)
    return JsonResponse({'id': message.id}, status=201)


# ----------------------------------------------------------------------
# Mail de l'usager : il écrit à un guichet (ou à la mairie) et lit les réponses
# ----------------------------------------------------------------------
MAIL_SUBJECT_MAX = 255
MAIL_BODY_MAX = 5000


def _mail_services():
    """Destinataires possibles : les guichets puis l'administration."""
    from agents.guichets import GUICHETS

    services = [{'value': str(number), 'label': f'{g.title} — {g.label}'} for number, g in GUICHETS.items()]
    services.append({'value': 'mairie', 'label': str(_('Administration de la mairie'))})
    return services


def _mail_recipients(service):
    """Comptes qui reçoivent le message : les agents du guichet, ou les administrateurs."""
    from django.contrib.auth import get_user_model

    users = get_user_model().objects.filter(is_active=True)
    if service == 'mairie':
        return list(users.filter(is_staff=True))
    return list(users.filter(agent_profile__guichet=int(service)))


def serialize_mail(mail, labels):
    return {
        'id': mail.id,
        'folder': 'sent' if mail.folder == mail.Folder.SENT else 'inbox',
        'service': mail.service,
        'service_label': labels.get(mail.service, ''),
        'sender_name': mail.sender_name,
        'subject': mail.subject,
        'body': mail.body,
        'created_at': _iso(mail.created_at),
        'is_read': mail.is_read,
    }


@clerk_auth_required
@require_http_methods(['GET', 'POST'])
def mail_collection(request):
    """GET : messages de l'usager (reçus et envoyés) ; POST : nouveau message à un guichet ou à la mairie."""
    from messagerie.models import Mail

    services = _mail_services()
    labels = {item['value']: item['label'] for item in services}
    if request.method == 'GET':
        mails = Mail.objects.filter(owner=None, citizen_id=request.clerk_user_id)[:MAX_LIST_RESULTS]
        return JsonResponse({'results': [serialize_mail(mail, labels) for mail in mails], 'services': services})

    limit, window = getattr(settings, 'MAIL_RATE_LIMIT', (20, 3600))
    if is_rate_limited(f'mail-rate:{request.clerk_user_id}', limit, window):
        return json_error('throttled', 429)
    data = _read_json_object(request)
    if data is None:
        return _invalid_json_response()

    errors = {}
    service = data.get('service')
    if service not in labels:
        errors['service'] = [REQUIRED if not service else INVALID]
    values = {}
    for name, limit_ in (('subject', MAIL_SUBJECT_MAX), ('body', MAIL_BODY_MAX),
                         ('sender_name', 150), ('sender_email', 254)):
        value = data.get(name, '')
        value = value.strip() if isinstance(value, str) else ''
        if len(value) > limit_:
            errors[name] = ['too_long']
        values[name] = value
    for name in ('subject', 'body'):
        if not values[name] and name not in errors:
            errors[name] = [REQUIRED]

    # Nom et e-mail : ceux du compte (envoyés par le frontend), sinon l'identité de sa dernière demande.
    identity = (
        DossierRequest.objects.filter(clerk_user_id=request.clerk_user_id)
        .values_list('identity', flat=True).first() or {}
    )
    name = values['sender_name'] or f"{identity.get('first_name', '')} {identity.get('last_name', '')}".strip()
    email = values['sender_email'] or identity.get('email', '')
    if email:
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        try:
            validate_email(email)
        except ValidationError:
            errors['sender_email'] = [INVALID]
    if errors:
        return JsonResponse({'errors': errors}, status=400)

    sent = Mail.objects.create(
        owner=None, citizen_id=request.clerk_user_id, service=service, folder=Mail.Folder.SENT,
        sender_name=name or str(_('Usager')), sender_email=email, to=labels[service],
        subject=values['subject'], body=values['body'],
    )
    for account in _mail_recipients(service):
        Mail.objects.create(
            owner=account, citizen_id=request.clerk_user_id, service=service, folder=Mail.Folder.INBOX,
            sender_name=sent.sender_name, sender_email=email, to=account.email or labels[service],
            subject=sent.subject, body=sent.body, created_at=sent.created_at, is_read=False,
        )
    return JsonResponse(serialize_mail(sent, labels), status=201)


@clerk_auth_required
@require_POST
def mail_mark_read(request, pk):
    """Marque un message reçu comme lu (404 si ce n'est pas le sien)."""
    from messagerie.models import Mail

    mails = Mail.objects.filter(pk=pk, owner=None, citizen_id=request.clerk_user_id)
    if not mails.exists():
        return json_error('not_found', 404)
    mails.update(is_read=True)
    return JsonResponse({'ok': True})


@clerk_auth_required
@require_POST
def assistant(request):
    """Assistant IA de l'usager : {"message"} → {"text", "items"}."""
    from .assistant import answer

    limit, window = getattr(settings, 'ASSISTANT_RATE_LIMIT', (120, 3600))
    if is_rate_limited(f'assistant-rate:{request.clerk_user_id}', limit, window):
        return json_error('throttled', 429)
    data = _read_json_object(request)
    if data is None:
        return _invalid_json_response()
    message = data.get('message', '')
    if not isinstance(message, str) or not message.strip():
        return JsonResponse({'errors': {'message': [REQUIRED]}}, status=400)
    return JsonResponse(answer(request.clerk_user_id, message[:1000]))
