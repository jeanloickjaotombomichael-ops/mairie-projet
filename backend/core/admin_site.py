"""Site d'administration de Mairy Project : tableau de bord, analyse et menu latéral."""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.urls import NoReverseMatch, path, reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _

from . import dashboard, people, security

# Menu latéral : (section, [(libellé, icône, nom d'URL, permission requise, clé du badge)]).
NAV_SECTIONS = [
    (_('Tableau de bord'), [
        (_('Accueil'), 'home', 'admin:index', None, None),
        (_('Analyse'), 'trend', 'admin:analytics', None, None),
    ]),
    (_('Menu rapide'), [
        (_('Utilisateurs'), 'user', 'admin:auth_user_changelist', 'auth.view_user', None),
        (_('Agents municipaux'), 'badge', 'admin:agents_agentprofile_changelist', 'agents.view_agentprofile', None),
        (_("Demandes d'accès agent"), 'users', 'admin:documents_agentaccessrequest_changelist',
         'documents.view_agentaccessrequest', 'agents'),
    ]),
    (_('Notifications'), [
        (_('Mail'), 'mail', 'admin:mail', None, 'inbox'),
        (_('Messages'), 'message', 'admin:espace_dossierrequest_changelist', 'espace.view_dossierrequest', 'pending'),
    ]),
    (_('Documents officiels'), [
        (_('Actes de naissance'), 'doc', 'admin:agents_birthcertificate_changelist',
         'agents.view_birthcertificate', 'deletions_birthcertificate'),
        (_('Actes de mariage'), 'doc', 'admin:agents_marriagecertificate_changelist',
         'agents.view_marriagecertificate', 'deletions_marriagecertificate'),
        (_('Actes de décès'), 'doc', 'admin:agents_deathcertificate_changelist',
         'agents.view_deathcertificate', 'deletions_deathcertificate'),
        (_('Législation'), 'doc', 'admin:agents_legislationextract_changelist',
         'agents.view_legislationextract', 'deletions_legislationextract'),
        (_('Attestations (guichet 5)'), 'doc', 'admin:agents_servicecertificate_changelist',
         'agents.view_servicecertificate', 'deletions_servicecertificate'),
    ]),
    (_('Sécurité'), [
        (_('Sécurité et fraude'), 'shield', 'admin:security', 'documents.view_documentauditlog', None),
    ]),
    (_('Autres fonctionnalités'), [
        (_("Journal d'audit"), 'report', 'admin:documents_documentauditlog_changelist',
         'documents.view_documentauditlog', None),
        (_('Groupes'), 'users', 'admin:auth_group_changelist', 'auth.view_group', None),
    ]),
]


class MairyAdminSite(admin.AdminSite):
    site_header = _('Mairie de Mahajanga — Administration')
    site_title = 'Mairy Project'
    index_title = _('Tableau de bord')
    # Le menu latéral de Django est remplacé par celui de base_site.html.
    enable_nav_sidebar = False

    def login(self, request, extra_context=None):
        # Une seule page de connexion pour tous : /connexion/ redirige selon le rôle.
        if request.method == 'GET':
            next_url = request.GET.get('next') or reverse('admin:index', current_app=self.name)
            return redirect(f"{reverse('connexion')}?{urlencode({'next': next_url})}")
        return super().login(request, extra_context)

    def logout(self, request, extra_context=None):
        # Après la déconnexion : retour direct à la page d'accueil (et non à la page « Déconnecté » de Django).
        from django.contrib.auth.views import LogoutView

        return LogoutView.as_view(next_page='home')(request)

    def get_urls(self):
        return [
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
            path('mail/', self.admin_view(self.mail_view), name='mail'),
            path('securite/', self.admin_view(self.security_view), name='security'),
            *super().get_urls(),
        ]

    def _badges(self, request):
        from documents.models import AgentAccessRequest
        from espace.models import ContactMessage, DossierRequest

        user = request.user
        badges = {}
        from messagerie.views import unread_count

        badges['inbox'] = unread_count(user)
        if user.has_perm('espace.view_dossierrequest'):
            badges['pending'] = DossierRequest.objects.filter(status=DossierRequest.Status.PENDING).count()
        if user.has_perm('espace.view_contactmessage'):
            badges['mail'] = ContactMessage.objects.filter(handled=False).count()
        from agents.official import DOCUMENT_MODELS

        for model in DOCUMENT_MODELS:
            if user.has_perm(f'agents.view_{model._meta.model_name}'):
                badges[f'deletions_{model._meta.model_name}'] = model.objects.filter(
                    deletion_requested_at__isnull=False, deleted_at=None,
                ).count()
        if user.has_perm('documents.view_agentaccessrequest'):
            badges['agents'] = AgentAccessRequest.objects.filter(status=AgentAccessRequest.Status.PENDING).count()
        return badges

    def each_context(self, request):
        context = super().each_context(request)
        # Utilisé aussi par la page de connexion (liens vers le site public).
        context['frontend_url'] = settings.FRONTEND_URL
        if not context.get('has_permission'):
            return context

        badges = self._badges(request)
        index_url = reverse('admin:index', current_app=self.name)
        sections = []
        for title, entries in NAV_SECTIONS:
            items = []
            for label, icon, url_name, perm, badge in entries:
                if perm and not request.user.has_perm(perm):
                    continue
                try:
                    url = reverse(url_name, current_app=self.name)
                except NoReverseMatch:
                    continue
                active = request.path == url if url == index_url else request.path.startswith(url)
                items.append({
                    'label': label,
                    'icon': icon,
                    'url': url,
                    'active': active,
                    'badge': badges.get(badge, 0) if badge else 0,
                })
            if items:
                sections.append({'title': title, 'items': items})

        context.update({
            'mairy_nav': sections,
            'mairy_badges': badges,
        })
        return context

    def index(self, request, extra_context=None):
        from documents.models import Document
        from espace.models import ContactMessage, DossierRequest

        user = request.user
        cards = []
        if user.has_perm('documents.view_document'):
            cards.append(dashboard.kpi(
                Document.all_objects.all(), 'issue_date', _('Documents émis'),
                reverse('admin:documents_document_changelist', current_app=self.name),
            ))
        if user.has_perm('espace.view_dossierrequest'):
            cards.append(dashboard.kpi(
                DossierRequest.objects.all(), 'created_at', _('Demandes de dossiers'),
                reverse('admin:espace_dossierrequest_changelist', current_app=self.name),
            ))
        if user.has_perm('espace.view_contactmessage'):
            cards.append(dashboard.kpi(
                ContactMessage.objects.all(), 'created_at', _('Messages reçus'),
                reverse('admin:espace_contactmessage_changelist', current_app=self.name),
            ))

        context = {
            'kpi_cards': cards,
            'chart': None,
            'new_members': [],
            'latest_requests': [],
        }
        if user.has_perm('espace.view_dossierrequest'):
            context['chart'] = dashboard.line_chart(
                dashboard.monthly_counts(DossierRequest.objects.all(), 'created_at')
            )
            context['latest_requests'] = DossierRequest.objects.all()[:6]
        if user.has_perm('auth.view_user'):
            context['new_members'] = get_user_model().objects.order_by('-date_joined')[:6]

        return super().index(request, {**context, **(extra_context or {})})

    def analytics_view(self, request):
        from documents.models import Document, DocumentAuditLog
        from espace.models import DossierRequest

        user = request.user
        context = {
            **self.each_context(request),
            'title': _('Analyse'),
            'charts': [],
            'breakdowns': [],
            'totals': [],
        }

        if user.has_perm('auth.view_user'):
            context['totals'].append({'label': _('Utilisateurs'), 'value': get_user_model().objects.count()})

        if user.has_perm('documents.view_document'):
            documents = Document.all_objects.all()
            context['totals'].append({
                'label': _('Documents actifs'),
                'value': Document.objects.filter(status=Document.Status.ACTIVE).count(),
            })
            context['charts'].append({
                'title': _('Documents émis par mois'),
                'chart': dashboard.line_chart(dashboard.monthly_counts(documents, 'issue_date')),
            })
            context['breakdowns'].append({
                'title': _('Documents par type'),
                **dashboard.breakdown(documents, 'document_type', Document.DocumentType.choices),
            })
            context['breakdowns'].append({
                'title': _('Documents par statut'),
                **dashboard.breakdown(documents, 'status', Document.Status.choices),
            })

        if user.has_perm('documents.view_documentauditlog'):
            logs = DocumentAuditLog.objects.all()
            context['totals'].append({
                'label': _('Vérifications réussies'),
                'value': logs.filter(action=DocumentAuditLog.Action.VERIFIED_SUCCESS).count(),
            })
            context['totals'].append({
                'label': _('Fraudes détectées'),
                'value': logs.filter(action=DocumentAuditLog.Action.VERIFIED_FRAUD).count(),
            })
            context['charts'].append({
                'title': _('Vérifications de documents par mois'),
                'chart': dashboard.line_chart(dashboard.monthly_counts(
                    logs.filter(action__in=[
                        DocumentAuditLog.Action.VERIFIED_SUCCESS,
                        DocumentAuditLog.Action.VERIFIED_FRAUD,
                    ]),
                    'timestamp',
                )),
            })

        if user.has_perm('espace.view_dossierrequest'):
            requests = DossierRequest.objects.all()
            context['breakdowns'].append({
                'title': _('Demandes par statut'),
                **dashboard.breakdown(requests, 'status', DossierRequest.Status.choices),
            })
            context['breakdowns'].append({
                'title': _('Demandes par type de dossier'),
                **dashboard.breakdown(requests, 'dossier_type', DossierRequest.DossierType.choices),
            })

        request.current_app = self.name
        return TemplateResponse(request, 'admin/analytics.html', context)

    def mail_view(self, request):
        """« Mail » : boîte mail de l'administrateur (à la manière de Gmail), avec l'annuaire en suggestions."""
        from messagerie.views import mailbox

        contacts = [
            {'email': p['email'], 'name': p['name']}
            for p in people.collect() if p['email'] and p['email'].lower() != (request.user.email or '').lower()
        ]
        request.current_app = self.name
        context = {**self.each_context(request), 'title': _('Mail')}
        return mailbox(request, 'admin/mail.html', context, contacts)

    def security_view(self, request):
        """« Sécurité et fraude » : intégrité des documents établis par les agents."""
        from django.core.exceptions import PermissionDenied
        from documents.models import DocumentAuditLog

        if not request.user.has_perm('documents.view_documentauditlog'):
            raise PermissionDenied

        rows = security.analyse_documents(self.name)
        groups = {
            '': (_('Tous les documents'), rows),
            'alertes': (_('Alertes'), [row for row in rows if row['level'] != security.OK]),
            'alteres': (_('Altérés (fraude)'), [row for row in rows if row['level'] == security.ALTERED]),
            'suppressions': (_('Suppressions demandées'), [row for row in rows if row['level'] == security.DELETION]),
        }
        current = request.GET.get('vue', '')
        if current not in groups:
            current = ''
        query = request.GET.get('q', '').strip().lower()
        shown = groups[current][1]
        if query:
            shown = [
                row for row in shown
                if query in row['number'].lower() or query in row['holder'].lower() or query in row['agent'].lower()
            ]

        logs = DocumentAuditLog.objects.all()
        context = {
            **self.each_context(request),
            'title': _('Sécurité et fraude'),
            'tabs': [
                {'value': value, 'label': label, 'count': len(items), 'active': value == current}
                for value, (label, items) in groups.items()
            ],
            'current': current,
            'query': request.GET.get('q', '').strip(),
            'rows': shown,
            'agents': security.agents_summary(rows),
            'verified_ok': logs.filter(action=DocumentAuditLog.Action.VERIFIED_SUCCESS).count(),
            'verified_fraud': logs.filter(action=DocumentAuditLog.Action.VERIFIED_FRAUD).count(),
            'recent_frauds': logs.filter(action=DocumentAuditLog.Action.VERIFIED_FRAUD)[:10],
        }
        request.current_app = self.name
        return TemplateResponse(request, 'admin/security.html', context)
