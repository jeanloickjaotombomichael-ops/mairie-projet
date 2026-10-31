from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.html import format_html

from agents.accounts import create_agent_account

from .models import AgentAccessRequest, Document, DocumentAuditLog

# Champs entrant dans l'empreinte : verrouillés après la création.
SEALED_FIELDS = (
    'document_type',
    'holder_first_name',
    'holder_last_name',
    'holder_national_id',
    'issue_date',
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'holder_full_name', 'document_type', 'status', 'issue_date', 'expiry_date', 'is_deleted')
    list_filter = ('document_type', 'status', 'is_deleted')
    search_fields = ('holder_first_name', 'holder_last_name', 'holder_national_id')
    date_hierarchy = 'issue_date'
    actions = ['revoke_documents']
    base_readonly_fields = (
        'id', 'verification_link', 'content_hash', 'signature',
        'is_deleted', 'deleted_at', 'created_at',
    )

    def get_queryset(self, request):
        # Le staff voit aussi les documents supprimés (filtrables).
        queryset = Document.all_objects.all()
        ordering = self.get_ordering(request)
        if ordering:
            queryset = queryset.order_by(*ordering)
        return queryset

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.base_readonly_fields)
        if obj is not None:
            readonly.extend(SEALED_FIELDS)
        return readonly

    @admin.display(description='ID')
    def short_id(self, obj):
        return str(obj.id)[:8]

    @admin.display(description=_('Titulaire'))
    def holder_full_name(self, obj):
        return f'{obj.holder_first_name} {obj.holder_last_name}'

    @admin.display(description=_('Lien de vérification'))
    def verification_link(self, obj):
        if obj is None or obj._state.adding:
            return '—'
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener noreferrer">{0}</a>',
            obj.verification_url,
        )

    @admin.action(description=_('Révoquer les documents sélectionnés'))
    def revoke_documents(self, request, queryset):
        count = 0
        for document in queryset.exclude(status=Document.Status.REVOKED):
            Document.all_objects.filter(pk=document.pk).update(status=Document.Status.REVOKED)
            DocumentAuditLog.objects.create(
                document=document,
                action=DocumentAuditLog.Action.REVOKED,
                performed_by=request.user,
                details=_('Révocation depuis l\'administration.'),
            )
            count += 1
        self.message_user(request, _('%(count)s document(s) révoqué(s).') % {'count': count}, messages.SUCCESS)

    def delete_model(self, request, obj):
        obj.soft_delete()
        DocumentAuditLog.objects.create(
            document=obj,
            action=DocumentAuditLog.Action.DELETED,
            performed_by=request.user,
            details=_('Suppression logique depuis l\'administration.'),
        )

    def delete_queryset(self, request, queryset):
        for document in queryset:
            self.delete_model(request, document)


@admin.register(DocumentAuditLog)
class DocumentAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'document', 'performed_by', 'ip_address')
    list_filter = ('action',)
    search_fields = ('details', 'ip_address')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AgentAccessRequest)
class AgentAccessRequestAdmin(admin.ModelAdmin):
    """Demandes d'accès agent : l'administrateur attribue le guichet puis approuve (le compte est créé)."""

    list_display = ('last_name', 'first_name', 'email', 'phone_number', 'guichet', 'status', 'compte', 'created_at')
    list_editable = ('guichet',)  # l'administrateur attribue le guichet avant d'approuver
    list_filter = ('status', 'guichet')
    search_fields = ('first_name', 'last_name', 'email', 'phone_number')
    readonly_fields = ('created_at', 'reviewed_at', 'agent_user')
    fields = (
        'first_name', 'last_name', 'email', 'phone_number', 'request_type', 'message',
        'guichet', 'status', 'agent_user', 'created_at', 'reviewed_at',
    )
    actions = ['approve_requests', 'reject_requests']

    @admin.display(description=_('Compte agent'))
    def compte(self, obj):
        return obj.agent_user.get_username() if obj.agent_user else '—'

    @admin.action(description=_('Approuver et créer les comptes agents'))
    def approve_requests(self, request, queryset):
        created = 0
        for access_request in queryset.filter(status=AgentAccessRequest.Status.PENDING):
            if not access_request.guichet:
                self.message_user(
                    request,
                    "%(request)s : attribuez d'abord un guichet (colonne « Guichet » de la liste, puis « Enregistrer »), puis approuvez."
                    % {'request': access_request},
                    messages.WARNING,
                )
                continue
            user, password = create_agent_account(access_request)
            access_request.agent_user = user
            access_request.status = AgentAccessRequest.Status.APPROVED
            access_request.reviewed_at = timezone.now()
            access_request.password_hash = ''  # repris par le compte : inutile de le garder ici
            access_request.save(update_fields=['agent_user', 'status', 'reviewed_at', 'password_hash'])
            created += 1
            if password is None:
                self.message_user(
                    request,
                    format_html(
                        _("Compte créé pour {} — Guichet {} : l'agent se connecte avec <strong>{}</strong> "
                          "et le mot de passe qu'il a choisi."),
                        access_request, access_request.guichet, user.get_username(),
                    ),
                    messages.SUCCESS,
                )
            else:
                # Demande envoyée depuis le site, sans mot de passe : provisoire, affiché une seule fois.
                self.message_user(
                    request,
                    format_html(
                        _("Compte créé pour {} — Guichet {} : identifiant <strong>{}</strong>, "
                          "mot de passe provisoire <strong>{}</strong> (à transmettre à l'agent ; "
                          "il ne sera plus affiché)."),
                        access_request, access_request.guichet, user.get_username(), password,
                    ),
                    messages.SUCCESS,
                )
        if not created:
            self.message_user(request, _('Aucun compte créé (seules les demandes en attente sont approuvées).'), messages.INFO)

    @admin.action(description=_('Rejeter les demandes sélectionnées'))
    def reject_requests(self, request, queryset):
        count = queryset.filter(status=AgentAccessRequest.Status.PENDING).update(
            status=AgentAccessRequest.Status.REJECTED, reviewed_at=timezone.now(), password_hash='',
        )
        self.message_user(request, _('%(count)s demande(s) rejetée(s).') % {'count': count}, messages.SUCCESS)
