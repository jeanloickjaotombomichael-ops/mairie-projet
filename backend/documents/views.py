"""API JSON de Mairy Project (sans Django REST Framework)."""
import io
import ipaddress
import json
import re
import uuid
from functools import wraps

from django import forms
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from agents.official import find_document

from .models import AgentAccessRequest, Document, DocumentAuditLog

UUID_PATTERN = re.compile(
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
)

MAX_SCAN_FILE_SIZE = 10 * 1024 * 1024  # 10 Mo


# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------
def json_error(detail, status):
    return JsonResponse({'detail': detail}, status=status)


def get_client_ip(request):
    """IP du client (X-Forwarded-For si présent), ou None si invalide.

    X-Forwarded-For n'est fiable que derrière un proxy de confiance.
    """
    candidates = []
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        candidates.append(forwarded.split(',')[0].strip())
    candidates.append(request.META.get('REMOTE_ADDR'))
    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(candidate))
        except (ValueError, TypeError):
            continue
    return None


def staff_json_required(view):
    """Réserve une vue au staff ; répond en JSON (401/403), sans redirection."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return json_error('authentication_required', 401)
        if not user.is_staff:
            return json_error('forbidden', 403)
        return view(request, *args, **kwargs)

    return wrapper


def build_verification_payload(request, document, result):
    payload = {
        'id': str(document.id),
        'is_authentic': result['is_authentic'],
        'status': result['status'],
        'hash_matches': result['hash_matches'],
        'signature_valid': result['signature_valid'],
        'document': None,
    }
    # Les données personnelles ne sont exposées que pour un document authentique.
    if result['is_authentic']:
        photo_url = None
        if document.holder_photo:
            photo_url = request.build_absolute_uri(document.holder_photo.url)
        pdf_url = None
        if document.pdf_file:
            pdf_url = request.build_absolute_uri(document.pdf_file.url)
        payload['document'] = {
            'document_type': document.document_type,
            'document_type_label': document.get_document_type_display(),
            'holder_first_name': document.holder_first_name,
            'holder_last_name': document.holder_last_name,
            'holder_national_id': document.holder_national_id or None,
            'holder_photo_url': photo_url,
            'issue_date': document.issue_date.isoformat(),
            'signature_fingerprint': document.content_hash,
            'pdf_url': pdf_url,
        }
    return payload


def log_verification(request, document, result, performed_by=None, prefix=''):
    DocumentAuditLog.objects.create(
        document=document,
        action=(
            DocumentAuditLog.Action.VERIFIED_SUCCESS
            if result['is_authentic']
            else DocumentAuditLog.Action.VERIFIED_FRAUD
        ),
        performed_by=performed_by,
        ip_address=get_client_ip(request),
        details=(
            f"{prefix}hash_matches={result['hash_matches']}, "
            f"signature_valid={result['signature_valid']}, "
            f"status={result['status']}"
        ),
    )


def log_unknown_uuid(request, token, performed_by=None, prefix=''):
    DocumentAuditLog.objects.create(
        document=None,
        action=DocumentAuditLog.Action.VERIFIED_FRAUD,
        performed_by=performed_by,
        ip_address=get_client_ip(request),
        details=f'{prefix}Unknown UUID verified: {token}',
    )


# ----------------------------------------------------------------------
# Vues publiques
# ----------------------------------------------------------------------
@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})


def build_official_document_payload(act, result):
    """Même format que build_verification_payload, pour un document établi à un guichet."""
    payload = {
        'id': str(act.id),
        'is_authentic': result['is_authentic'],
        'status': result['status'],
        'hash_matches': result['hash_matches'],
        'signature_valid': result['signature_valid'],
        'document': None,
    }
    if result['is_authentic']:
        payload['document'] = {
            'document_type': act.DOCUMENT_CODE,
            'document_type_label': act.label,
            'holder_first_name': '',
            'holder_last_name': act.holder_name,
            'holder_national_id': None,
            'holder_photo_url': None,
            'issue_date': act.act_datetime.isoformat(),
            'signature_fingerprint': act.content_hash,
            'pdf_url': None,
        }
    return payload


@require_GET
def verify_document(request, token):
    # Documents établis par les agents des guichets (QR code du PDF).
    act = find_document(token)
    if act is not None:
        result = act.verify()
        DocumentAuditLog.objects.create(
            document=None,
            action=(
                DocumentAuditLog.Action.VERIFIED_SUCCESS if result['is_authentic']
                else DocumentAuditLog.Action.VERIFIED_FRAUD
            ),
            ip_address=get_client_ip(request),
            details=f"{act.label} {act.act_number} : status={result['status']}",
        )
        return JsonResponse(build_official_document_payload(act, result))

    document = Document.objects.filter(id=token).first()

    if document is None:
        log_unknown_uuid(request, token)
        return json_error('not_found', 404)

    result = document.verify_authenticity()
    log_verification(request, document, result)
    return JsonResponse(build_verification_payload(request, document, result))


class AgentAccessForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    phone_number = forms.RegexField(
        regex=r'^[0-9+()\-.\s]{6,30}$',
        max_length=30,
        error_messages={'invalid': 'Saisissez un numéro de téléphone valide.'},
    )
    email = forms.EmailField(max_length=254)
    request_type = forms.ChoiceField(choices=AgentAccessRequest.REQUEST_TYPE_CHOICES)
    message = forms.CharField(max_length=2000, required=False)


def _is_rate_limited(request):
    limit, window = getattr(settings, 'AGENT_REQUEST_RATE_LIMIT', (10, 3600))
    key = f"agent-request-rate:{get_client_ip(request) or 'unknown'}"
    cache.add(key, 0, timeout=window)
    try:
        count = cache.incr(key)
    except ValueError:  # la clé a expiré entre add() et incr()
        cache.set(key, 1, timeout=window)
        count = 1
    return count > limit


@csrf_exempt  # endpoint public, sans session ni cookie : le CSRF ne s'applique pas
@require_POST
def agent_request_create(request):
    if _is_rate_limited(request):
        return json_error('throttled', 429)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        data = None
    if not isinstance(data, dict):
        return JsonResponse({'errors': {'__all__': ['invalid_json']}}, status=400)

    form = AgentAccessForm(data)
    if not form.is_valid():
        errors = {field: [str(message) for message in messages] for field, messages in form.errors.items()}
        return JsonResponse({'errors': errors}, status=400)

    agent_request = AgentAccessRequest.objects.create(**form.cleaned_data)
    return JsonResponse({'id': agent_request.id}, status=201)


@require_GET
def document_qr(request, token):
    document = Document.objects.filter(id=token).first()
    if document is None:
        return json_error('not_found', 404)

    try:
        import qrcode
    except ImportError:
        return json_error('qrcode_unavailable', 501)

    image = qrcode.make(document.verification_url)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')

    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Cache-Control'] = 'public, max-age=3600'
    return response


# ----------------------------------------------------------------------
# Vues réservées au staff
# ----------------------------------------------------------------------
def _first_uuid(text):
    match = UUID_PATTERN.search(text or '')
    return uuid.UUID(match.group(0)) if match else None


def extract_uuid_from_file(uploaded_file):
    """Extrait un UUID d'un PDF (texte) ou d'une image (QR code)."""
    name = (uploaded_file.name or '').lower()

    if name.endswith('.pdf'):
        try:
            from pypdf import PdfReader

            uploaded_file.seek(0)
            reader = PdfReader(uploaded_file)
            text = '\n'.join((page.extract_text() or '') for page in reader.pages)
            return _first_uuid(text)
        except Exception:
            return None

    try:
        from PIL import Image
        from pyzbar.pyzbar import decode as decode_qr

        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        for decoded in decode_qr(image):
            found = _first_uuid(decoded.data.decode('utf-8', errors='ignore'))
            if found:
                return found
    except Exception:
        return None
    return None


@require_POST
@staff_json_required
def fraud_scan(request):
    uploaded = request.FILES.get('target_file')
    if uploaded is None:
        return json_error('missing_file', 400)
    if uploaded.size > MAX_SCAN_FILE_SIZE:
        return json_error('file_too_large', 413)

    token = extract_uuid_from_file(uploaded)
    if token is None:
        return JsonResponse({'detail': 'no_uuid_found', 'filename': uploaded.name}, status=400)

    prefix = 'Fraud-detection scan: '
    document = Document.all_objects.filter(id=token).first()

    if document is None:
        log_unknown_uuid(request, token, performed_by=request.user, prefix=prefix)
        return JsonResponse({
            'id': str(token),
            'is_authentic': False,
            'status': Document.RESULT_INVALID,
            'hash_matches': False,
            'signature_valid': False,
            'document': None,
            'found': False,
            'filename': uploaded.name,
        })

    result = document.verify_authenticity()
    log_verification(request, document, result, performed_by=request.user, prefix=prefix)
    payload = build_verification_payload(request, document, result)
    payload['found'] = True
    payload['filename'] = uploaded.name
    return JsonResponse(payload)


@require_GET
@staff_json_required
def admin_stats(request):
    rows = (
        Document.objects
        .annotate(month=TruncMonth('issue_date'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )
    months = []
    totals = []
    for row in rows:
        if row['month']:
            months.append(row['month'].strftime('%Y-%m'))
            totals.append(row['total'])
    return JsonResponse({'months': months, 'totals': totals})
