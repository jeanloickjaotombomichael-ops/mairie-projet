"""Espace des agents municipaux : connexion commune, tableau de bord, demandes, actes, mail et messages."""
import base64
import datetime
import decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.formats import date_format
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core import dashboard
from documents.views import _is_rate_limited
from espace.models import DossierRequest
from espace.schemas import FOKONTANY
from fichiers.models import trash_count
from messagerie.views import mailbox, unread_count

from . import assistant as assistant_engine
from .access import agent_profile, guichet_required, home_url_for
from .forms import AgentProfileForm, AgentSignupForm, ConnexionForm, DecisionForm
from .guichets import GUICHETS
from .labels import field_label, option_label
from .official import OFFICIAL_DOCUMENTS
from .queue import annotate_positions, blocked_message, blocking_request
from .pdf import document_pdf as document_pdf_bytes
from .pdf import qr_png

Status = DossierRequest.Status


# Onglets de la liste des demandes : (valeur du filtre, libellé).
STATUS_TABS = [
    ('', _('Toutes')),
    (Status.PENDING, _('En attente')),
    (Status.IN_PROGRESS, _('En cours')),
    (Status.APPROVED, _('Approuvées')),
    (Status.REJECTED, _('Refusées')),
    (Status.COMPLETED, _('Terminées')),
]


# ---------------------------------------------------------------------------
# Connexion commune (administrateurs et agents)
# ---------------------------------------------------------------------------

class ConnexionView(LoginView):
    template_name = 'admin/login.html'
    authentication_form = ConnexionForm

    def dispatch(self, request, *args, **kwargs):
        # Déjà connecté avec un rôle : directement vers sa page.
        target = home_url_for(request.user) if request.user.is_authenticated else None
        if target and request.method == 'GET':
            return redirect(target)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        user = self.request.user
        next_url = self.get_redirect_url()
        # Un agent ne suit un « next » que vers l'espace agent (le guichet est revérifié à l'arrivée).
        if next_url and (user.is_staff or next_url.startswith('/agent/')):
            return next_url
        return home_url_for(user)

    def get_redirect_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next') or ''
        allowed = url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure(),
        )
        return next_url if allowed else ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'app_path': self.request.get_full_path(),
            'site_title': 'Mairy Project',
            'frontend_url': settings.FRONTEND_URL,
        })
        return context


def inscription(request):
    """Demande d'accès d'un agent (publique) : il choisit ses identifiants, l'administrateur valide."""
    if home_url_for(request.user):
        return redirect(home_url_for(request.user))

    if request.method == 'POST':
        form = AgentSignupForm(request.POST)
        if _is_rate_limited(request):
            form.is_valid()
            form.add_error(None, _('Trop de demandes envoyées. Réessayez plus tard.'))
        elif form.is_valid():
            access_request = form.save()
            return render(request, 'agents/inscription.html', {'sent': access_request})
    else:
        form = AgentSignupForm()
    return render(request, 'agents/inscription.html', {'form': form})


class DeconnexionView(LogoutView):
    next_page = 'home'


@login_required
def agent_home(request):
    """/agent/ : renvoie l'agent vers son guichet."""
    target = home_url_for(request.user)
    if target is None:
        return render(request, 'agents/forbidden.html', {'reason': 'no_role'}, status=403)
    return redirect(target)


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------

def _guichet_requests(guichet):
    return DossierRequest.objects.filter(dossier_type__in=guichet.dossier_types)


def _seen_at(request, number):
    """Dernière consultation des notifications du guichet (None : jamais)."""
    profile = agent_profile(request.user)
    if profile is not None and profile.guichet == number:
        return profile.notifications_seen_at
    stored = request.session.get(f'notifications_seen_{number}')
    return datetime.datetime.fromisoformat(stored) if stored else None


def _mark_seen(request, number):
    now = timezone.now()
    profile = agent_profile(request.user)
    if profile is not None and profile.guichet == number:
        profile.notifications_seen_at = now
        profile.save(update_fields=['notifications_seen_at'])
    else:
        request.session[f'notifications_seen_{number}'] = now.isoformat()


def _new_requests(request, number):
    """Demandes reçues par le guichet depuis la dernière consultation des notifications."""
    requests = _guichet_requests(GUICHETS[number])
    seen_at = _seen_at(request, number)
    return requests.filter(created_at__gt=seen_at) if seen_at else requests


def _request_stats(request, number, current):
    """Cartes de chiffres de « Toutes les demandes » : notifications, en attente, en cours."""
    requests = _guichet_requests(GUICHETS[number])
    list_url = reverse('agents:requests', args=[number])
    return [
        {'label': _('Notifications'), 'icon': 'bell', 'url': reverse('agents:notifications', args=[number]),
         'count': _new_requests(request, number).count(), 'unit': _('Non lues'), 'active': current == 'notifications'},
        {'label': _('En attente'), 'icon': 'message', 'url': f'{list_url}?statut={Status.PENDING}',
         'count': requests.filter(status=Status.PENDING).count(), 'unit': _('Demandes'),
         'active': current == Status.PENDING},
        {'label': _('En cours'), 'icon': 'trend', 'url': f'{list_url}?statut={Status.IN_PROGRESS}',
         'count': requests.filter(status=Status.IN_PROGRESS).count(), 'unit': _('Demandes'),
         'active': current == Status.IN_PROGRESS},
    ]


def _shell(request, number, active):
    """Contexte du cadre (barre du haut, menu latéral) commun aux pages de l'espace agent."""
    guichet = GUICHETS[number]
    requests = _guichet_requests(guichet)
    pending = requests.filter(status=Status.PENDING).count()
    new_count = _new_requests(request, number).count()
    list_url = reverse('agents:requests', args=[number])

    nav = [
        {'title': guichet.title, 'items': [
            {'label': _('Tableau de bord'), 'icon': 'home', 'url': reverse('agents:dashboard', args=[number]),
             'active': active == 'dashboard', 'badge': 0},
            {'label': _('Toutes les demandes'), 'icon': 'message', 'url': list_url,
             'active': active.startswith('requests:') or active == 'notifications', 'badge': 0},
        ]},
        {'title': _('Outils'), 'items': ([
            {'label': _('Documents officiels'), 'icon': 'doc', 'url': reverse('agents:documents', args=[number]),
             'active': active == 'documents', 'badge': 0},
        ] if number in OFFICIAL_DOCUMENTS else []) + [
            {'label': _('Mail'), 'icon': 'mail', 'url': reverse('agents:mail', args=[number]),
             'active': active == 'mail', 'badge': unread_count(request.user)},
            {'label': _('Messages'), 'icon': 'message', 'url': reverse('agents:messages', args=[number]),
             'active': active == 'messages', 'badge': 0},
        ]},
        {'title': _('Mes fichiers'), 'items': [
            {'label': _('Dossiers'), 'icon': 'folder', 'url': reverse('agents:folders', args=[number]),
             'active': active == 'folders', 'badge': 0},
            {'label': _('Corbeille'), 'icon': 'trash', 'url': reverse('agents:trash', args=[number]),
             'active': active == 'trash', 'badge': trash_count(request.user)},
        ]},
        {'title': _('Mon compte'), 'items': [
            {'label': _('Paramètres'), 'icon': 'gear', 'url': reverse('agents:settings'),
             'active': active == 'settings', 'badge': 0},
        ]},
    ]
    if request.user.is_superuser:
        nav.append({'title': _('Tous les guichets'), 'items': [
            {'label': f'{g.title} — {g.label}', 'icon': 'badge', 'url': reverse('agents:dashboard', args=[n]),
             'active': n == number and active == 'dashboard', 'badge': 0}
            for n, g in GUICHETS.items()
        ] + [{'label': _('Administration'), 'icon': 'report', 'url': reverse('admin:index'),
              'active': False, 'badge': 0}]})

    return {
        'guichet': guichet,
        'number': number,
        'mairy_nav': nav,
        'pending_count': pending,
        'new_count': new_count,
        'list_url': list_url,
        'frontend_url': settings.FRONTEND_URL,
    }


# Étape « Quartier » des demandes d'actes : affichée à part sur la fiche de la demande.
QUARTIER_KEYS = ('fokontany', 'main_residence')


def _labelled(values):
    """Valeurs d'un dictionnaire (identité, détails) avec leurs libellés français."""
    rows = []
    for key, value in (values or {}).items():
        if value in (None, ''):
            continue
        shown = option_label(value) if isinstance(value, str) else value
        rows.append({'label': field_label(key), 'value': shown})
    return rows


def _applicant(dossier):
    identity = dossier.identity or {}
    return f"{identity.get('last_name', '')} {identity.get('first_name', '')}".strip() or '—'


# ---------------------------------------------------------------------------
# Pages du guichet
# ---------------------------------------------------------------------------

@guichet_required
def guichet_dashboard(request, number):
    guichet = request.guichet
    requests = _guichet_requests(guichet)

    cards = [
        dashboard.kpi(requests, 'created_at', _('Demandes reçues'), reverse('agents:requests', args=[number])),
        dashboard.kpi(requests.exclude(responded_at=None), 'responded_at', _('Réponses envoyées'),
                      reverse('agents:requests', args=[number])),
    ]
    pending = requests.filter(status=Status.PENDING).count()

    latest = list(requests.order_by('-created_at')[:6])
    for dossier in latest:
        dossier.applicant = _applicant(dossier)
    annotate_positions(latest, guichet.dossier_types)

    context = {
        **_shell(request, number, 'dashboard'),
        'title': format_lazy('{} — {}', guichet.title, guichet.label),
        'kpi_cards': cards,
        'pending': pending,
        'chart': dashboard.line_chart(dashboard.monthly_counts(requests, 'created_at')),
        'by_status': dashboard.breakdown(requests, 'status', Status.choices),
        'by_type': (
            dashboard.breakdown(
                requests, 'dossier_type',
                [c for c in DossierRequest.DossierType.choices if c[0] in guichet.dossier_types],
            )
            if len(guichet.dossier_types) > 1 else None
        ),
        'latest_requests': latest,
    }
    return render(request, 'agents/dashboard.html', context)


@guichet_required
def guichet_requests(request, number):
    guichet = request.guichet
    status = request.GET.get('statut', '')
    if status not in Status.values:
        status = ''
    query = request.GET.get('q', '').strip()
    # Guichets des actes (1 à 4) : filtre par fokontany (étape « Quartier » du formulaire).
    fokontany = request.GET.get('fokontany', '') if number <= 4 else ''
    if fokontany not in FOKONTANY:
        fokontany = ''

    requests = _guichet_requests(guichet).order_by('-created_at')
    if status:
        requests = requests.filter(status=status)
    if fokontany:
        requests = requests.filter(details__fokontany=fokontany)
    if query:
        requests = requests.filter(
            Q(reference__icontains=query)
            | Q(identity__last_name__icontains=query)
            | Q(identity__first_name__icontains=query)
            | Q(identity__email__icontains=query)
            | Q(identity__phone__icontains=query)
        )

    page = Paginator(requests, 20).get_page(request.GET.get('page'))
    for dossier in page.object_list:
        dossier.applicant = _applicant(dossier)
    annotate_positions(page.object_list, guichet.dossier_types)

    context = {
        **_shell(request, number, f'requests:{status}'),
        'title': _('Demandes du guichet'),
        'request_stats': _request_stats(request, number, status),
        'tabs': [{'value': value, 'label': label, 'active': value == status} for value, label in STATUS_TABS],
        'status': status,
        'query': query,
        'fokontany': fokontany,
        'fokontany_choices': FOKONTANY if number <= 4 else (),
        'page': page,
    }
    return render(request, 'agents/requests.html', context)


@guichet_required
def guichet_request_detail(request, number, pk):
    guichet = request.guichet
    # Une demande d'un autre guichet est introuvable ici (404).
    dossier = get_object_or_404(_guichet_requests(guichet), pk=pk)
    # Premier arrivé, premier servi : une demande plus ancienne du même type attend encore.
    blocker = blocking_request(dossier)

    if request.method == 'POST' and blocker is not None:
        messages.error(request, blocked_message(blocker))
        return redirect('agents:request_detail', number, dossier.pk)
    if request.method == 'POST':
        form = DecisionForm(request.POST, instance=dossier)
        if form.is_valid():
            form.save()
            messages.success(request, _('Demande %(reference)s mise à jour.') % {'reference': dossier.reference})
            return redirect('agents:request_detail', number, dossier.pk)
    else:
        form = DecisionForm(instance=dossier)

    context = {
        **_shell(request, number, 'requests:'),
        'title': _('Demande %(reference)s') % {'reference': dossier.reference},
        'dossier': dossier,
        'applicant': _applicant(dossier),
        'identity_rows': _labelled(dossier.identity),
        'detail_rows': _labelled({k: v for k, v in (dossier.details or {}).items() if k not in QUARTIER_KEYS}),
        'quartier_rows': _labelled({k: v for k, v in (dossier.details or {}).items() if k in QUARTIER_KEYS}),
        'form': form,
        'blocker': blocker,
        'blocked_message': blocked_message(blocker) if blocker else '',
        # Ce guichet établit l'acte demandé : bouton « Établir l'acte » et actes déjà établis.
        'can_issue_document': number in OFFICIAL_DOCUMENTS,
        'issue_label': OFFICIAL_DOCUMENTS[number].issue_label if number in OFFICIAL_DOCUMENTS else '',
        'issued_documents': (
            OFFICIAL_DOCUMENTS[number].model.objects.filter(request=dossier, deleted_at=None)
            if number in OFFICIAL_DOCUMENTS else []
        ),
    }
    return render(request, 'agents/request_detail.html', context)


@login_required
def agent_settings(request):
    """Paramètres de l'agent : profil, mot de passe ; langue, apparence et alertes (préférences du navigateur)."""
    profile = agent_profile(request.user)
    if profile is None:
        if request.user.is_staff:
            return redirect('admin:password_change')
        return render(request, 'agents/forbidden.html', {'reason': 'no_role'}, status=403)

    profile_form = AgentProfileForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)
    if request.method == 'POST':
        if request.POST.get('section') == 'password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, _('Votre mot de passe a été modifié.'))
                return redirect('agents:settings')
        else:
            profile_form = AgentProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, _('Votre profil a été mis à jour.'))
                return redirect('agents:settings')

    context = {
        **_shell(request, profile.guichet, 'settings'),
        'title': _('Paramètres'),
        'profile_form': profile_form,
        'password_form': password_form,
    }
    return render(request, 'agents/settings.html', context)


# ---------------------------------------------------------------------------
# Documents officiels (un document par guichet, voir official.py)
# ---------------------------------------------------------------------------

def _spec(number):
    if number not in OFFICIAL_DOCUMENTS:
        raise Http404(_("Ce guichet n'établit pas de documents officiels."))
    return OFFICIAL_DOCUMENTS[number]


def _search(model, query):
    """Recherche dans le numéro et les champs texte du document."""
    condition = Q(act_number__icontains=query)
    for name in model.SEALED_FIELDS:
        if isinstance(model._meta.get_field(name), (models.CharField, models.TextField)):
            condition |= Q(**{f'{name}__icontains': query})
    return condition


def _display(document, name):
    """Valeur lisible d'un champ du document (choix, dates, montants)."""
    field = document._meta.get_field(name)
    value = getattr(document, name)
    if value in (None, ''):
        return ''
    if field.choices:
        return getattr(document, f'get_{name}_display')()
    if isinstance(value, datetime.datetime):
        return date_format(timezone.localtime(value), _('j F Y à H:i'))
    if isinstance(value, datetime.date):
        return date_format(value, _('j F Y'))
    if isinstance(value, decimal.Decimal):
        return f'{value:,.2f}'.replace(',', '\u202f').replace('.', ',') + ' Ar'
    return value


def _document_rows(document, spec):
    """Contenu du document, rubrique par rubrique (champs remplis seulement)."""
    sections = []
    for title, names in spec.form.SECTIONS:
        rows = [
            {'label': document._meta.get_field(name).verbose_name.capitalize(), 'value': _display(document, name)}
            for name in names
        ]
        rows = [row for row in rows if row['value'] != '']
        if rows:
            sections.append({'title': title, 'rows': rows})
    return sections


@guichet_required
def documents_list(request, number):
    spec = _spec(number)
    query = request.GET.get('q', '').strip()
    acts = spec.model.objects.filter(deleted_at=None)
    if query:
        acts = acts.filter(_search(spec.model, query))
    context = {
        **_shell(request, number, 'documents'),
        'title': _('Documents officiels'),
        'spec': spec,
        'page': Paginator(acts, 20).get_page(request.GET.get('page')),
        'query': query,
    }
    return render(request, 'agents/documents.html', context)


@guichet_required
def document_create(request, number):
    spec = _spec(number)
    origin = None
    origin_pk = request.POST.get('demande') or request.GET.get('demande')
    if origin_pk:
        origin = get_object_or_404(DossierRequest, pk=origin_pk, dossier_type__in=spec.request_types)
        blocker = blocking_request(origin)
        if blocker is not None:
            messages.error(request, blocked_message(blocker))
            return redirect('agents:request_detail', number, origin.pk)

    if request.method == 'POST':
        form = spec.form(request.POST)
        if form.is_valid():
            act = form.save(commit=False)
            act.created_by = request.user
            act.request = origin
            act.save()
            messages.success(request, _('%(document)s établi et scellé. Vous pouvez télécharger le PDF.') % {'document': act.label})
            return redirect('agents:document_detail', number, act.pk)
    else:
        initial = {'registrar_name': request.user.get_full_name()}
        if origin is not None:
            initial.update({key: value for key, value in spec.prefill(origin).items() if value not in ('', None)})
        form = spec.form(initial=initial)

    context = {
        **_shell(request, number, 'documents'),
        'title': spec.new_label,
        'spec': spec,
        'form': form,
        'origin': origin,
        'origin_applicant': _applicant(origin) if origin else '',
    }
    return render(request, 'agents/document_form.html', context)


@guichet_required
def document_detail(request, number, pk):
    spec = _spec(number)
    act = get_object_or_404(spec.model, pk=pk, deleted_at=None)
    qr = base64.b64encode(qr_png(act.verification_url)).decode('ascii')
    context = {
        **_shell(request, number, 'documents'),
        'title': act.label,
        'spec': spec,
        'act': act,
        'content_sections': _document_rows(act, spec),
        'check': act.verify(),
        'qr_data_uri': f'data:image/png;base64,{qr}',
        'recipient': _applicant(act.request) if act.request else '',
        'recipient_email': (act.request.identity or {}).get('email', '') if act.request else '',
        # Document établi sans demande : l'agent choisit la demande de l'usager à qui l'envoyer.
        'candidate_requests': [] if act.request else _send_candidates(spec),
        'default_message': _default_send_message(act),
    }
    return render(request, 'agents/document_detail.html', context)


@guichet_required
def document_pdf(request, number, pk):
    spec = _spec(number)
    act = get_object_or_404(spec.model, pk=pk, deleted_at=None)
    response = HttpResponse(document_pdf_bytes(act), content_type='application/pdf')
    disposition = 'inline' if request.GET.get('apercu') else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{act.filename}"'
    return response


@guichet_required
def document_delete(request, number, pk):
    """L'agent ne supprime pas lui-même : il demande la suppression, avec un motif, à l'administrateur."""
    spec = _spec(number)
    act = get_object_or_404(spec.model, pk=pk, deleted_at=None)
    if act.deletion_pending:
        messages.info(request, _("La suppression du document %(number)s attend déjà la décision de l'administrateur.") % {'number': act.act_number})
        return redirect('agents:document_detail', number, act.pk)

    error = ''
    reason = ''
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            error = _("Indiquez le motif de la suppression : l'administrateur en a besoin pour décider.")
        else:
            act.deletion_requested_at = timezone.now()
            act.deletion_requested_by = request.user
            act.deletion_reason = reason[:2000]
            act.save(update_fields=['deletion_requested_at', 'deletion_requested_by', 'deletion_reason'])
            messages.success(
                request,
                _("Demande de suppression du document %(number)s envoyée à l'administrateur.") % {'number': act.act_number},
            )
            return redirect('agents:document_detail', number, act.pk)

    context = {
        **_shell(request, number, 'documents'),
        'title': _('Supprimer le document %(number)s') % {'number': act.act_number},
        'act': act,
        'reason': reason,
        'error': error,
    }
    return render(request, 'agents/document_delete.html', context)


@require_POST
@guichet_required
def document_cancel_deletion(request, number, pk):
    spec = _spec(number)
    act = get_object_or_404(spec.model, pk=pk, deleted_at=None)
    if act.deletion_pending:
        act.deletion_requested_at = None
        act.deletion_requested_by = None
        act.deletion_reason = ''
        act.save(update_fields=['deletion_requested_at', 'deletion_requested_by', 'deletion_reason'])
        messages.success(request, _('Demande de suppression du document %(number)s annulée.') % {'number': act.act_number})
    return redirect('agents:document_detail', number, act.pk)


def _default_send_message(act):
    # Message destiné à l'usager (espace citoyen, en français) quelle que soit la langue de l'agent.
    with translation.override('fr'):
        label = str(act.label)
    return (
        f'Votre document « {label} » est disponible. '
        'Vous pouvez le télécharger dès maintenant depuis vos notifications.'
    )


def _send_candidates(spec):
    """Demandes du guichet auxquelles aucun document de ce type n'a encore été envoyé."""
    already_served = spec.model.objects.filter(deleted_at=None).exclude(sent_at=None).values('request_id')
    candidates = list(
        DossierRequest.objects.filter(dossier_type__in=spec.request_types)
        .exclude(pk__in=already_served)
        .order_by('-created_at')[:50]
    )
    for dossier in candidates:
        dossier.applicant = _applicant(dossier)
    return candidates


@require_POST
@guichet_required
def document_send(request, number, pk):
    """Envoie le document à l'usager de la demande : il le télécharge depuis ses notifications."""
    spec = _spec(number)
    act = get_object_or_404(spec.model, pk=pk, deleted_at=None)
    if act.deletion_pending or act.status != spec.model.Status.ACTIVE:
        messages.error(request, _('Ce document ne peut pas être envoyé (suppression demandée ou document révoqué).'))
        return redirect('agents:document_detail', number, act.pk)

    if act.request is None:
        dossier = DossierRequest.objects.filter(
            pk=request.POST.get('demande') or 0, dossier_type__in=spec.request_types,
        ).first()
        if dossier is None:
            messages.error(request, _("Choisissez la demande de l'usager à qui envoyer le document."))
            return redirect('agents:document_detail', number, act.pk)
        blocker = blocking_request(dossier)
        if blocker is not None:
            messages.error(request, blocked_message(blocker))
            return redirect('agents:document_detail', number, act.pk)
        act.request = dossier
    dossier = act.request

    act.sent_at = timezone.now()
    act.sent_by = request.user
    act.save(update_fields=['request', 'sent_at', 'sent_by'])

    # Réponse à l'usager : apparaît dans ses notifications, avec le bouton « Télécharger ».
    dossier.status = DossierRequest.Status.COMPLETED
    dossier.response_message = (request.POST.get('message') or '').strip()[:4000] or _default_send_message(act)
    dossier.save()
    # Même message qu'un envoi précédent : la notification doit tout de même réapparaître.
    DossierRequest.objects.filter(pk=dossier.pk).update(responded_at=act.sent_at, response_read=False)

    messages.success(
        request,
        _('%(document)s envoyé à %(person)s : il peut le télécharger depuis ses notifications.')
        % {'document': act.label, 'person': _applicant(dossier)},
    )
    return redirect('agents:document_detail', number, act.pk)


# ---------------------------------------------------------------------------
# Notifications : nouvelles demandes reçues par le guichet
# ---------------------------------------------------------------------------

def _notification(request, number, dossier):
    return {
        'reference': dossier.reference,
        'type': dossier.get_dossier_type_display(),
        'applicant': _applicant(dossier),
        'url': reverse('agents:request_detail', args=[number, dossier.pk]),
    }


@guichet_required
def guichet_notifications(request, number):
    seen_at = _seen_at(request, number)
    latest = list(_guichet_requests(request.guichet).order_by('-created_at')[:30])
    for dossier in latest:
        dossier.applicant = _applicant(dossier)
        dossier.is_new = seen_at is None or dossier.created_at > seen_at
    context = {
        **_shell(request, number, 'notifications'),
        'title': _('Notifications'),
        'request_stats': _request_stats(request, number, 'notifications'),
        'notifications': latest,
    }
    _mark_seen(request, number)  # consultées : la cloche repart de zéro
    return render(request, 'agents/notifications.html', context)


@guichet_required
def notifications_count(request, number):
    """Interrogé régulièrement par la page de l'agent : nombre de nouvelles demandes et la plus récente."""
    new = _new_requests(request, number).order_by('-created_at')
    latest = new.first()
    return JsonResponse({
        'new_count': new.count(),
        'latest': _notification(request, number, latest) if latest else None,
    })


# ---------------------------------------------------------------------------
# Mail : boîte mail de l'agent (à la manière de Gmail)
# ---------------------------------------------------------------------------

@guichet_required
def guichet_mail(request, number):
    """Suggestions de destinataires : les usagers du guichet, puis l'équipe (administrateurs et agents)."""
    from django.contrib.auth import get_user_model

    contacts = {}
    for dossier in _guichet_requests(request.guichet).order_by('-created_at'):
        email = ((dossier.identity or {}).get('email') or '').strip().lower()
        if email and email not in contacts:
            contacts[email] = {'email': email, 'name': _applicant(dossier)}
    for user in get_user_model().objects.filter(is_active=True).exclude(email='').exclude(pk=request.user.pk):
        contacts.setdefault(user.email.lower(), {'email': user.email, 'name': user.get_full_name() or user.username})

    context = {**_shell(request, number, 'mail'), 'title': _('Mail')}
    return mailbox(request, 'agents/mail.html', context, contacts.values())


# ---------------------------------------------------------------------------
# Messages : réponses envoyées aux usagers
# ---------------------------------------------------------------------------

MESSAGE_TABS = [('', _('Toutes')), ('non-lues', _('Non lues')), ('lues', _('Lues'))]


@guichet_required
def guichet_messages(request, number):
    current = request.GET.get('filtre', '')
    replies = _guichet_requests(request.guichet).exclude(response_message='').order_by('-responded_at')
    unread = replies.filter(response_read=False).count()
    if current == 'non-lues':
        replies = replies.filter(response_read=False)
    elif current == 'lues':
        replies = replies.filter(response_read=True)
    else:
        current = ''

    page = Paginator(replies, 20).get_page(request.GET.get('page'))
    for dossier in page.object_list:
        dossier.applicant = _applicant(dossier)

    without_reply = _guichet_requests(request.guichet).filter(response_message='').count()
    context = {
        **_shell(request, number, 'messages'),
        'title': _('Messages'),
        'tabs': [{'value': v, 'label': l, 'active': v == current} for v, l in MESSAGE_TABS],
        'page': page,
        'unread': unread,
        'without_reply': without_reply,
    }
    return render(request, 'agents/messages.html', context)


# ---------------------------------------------------------------------------
# Assistant IA (agents et administration)
# ---------------------------------------------------------------------------

@require_POST
@login_required
def assistant(request):
    """Échange avec l'assistant : {"message", "page"} ou {"confirm": {...}} → {"text", "items", "confirm"}."""
    import json

    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if data.get('confirm'):
        reply = assistant_engine.confirm(request.user, data['confirm'])
    else:
        reply = assistant_engine.answer(request.user, str(data.get('message', '')), str(data.get('page', '')))
    return JsonResponse(reply.as_json())
