from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import AgentProfile
from .official import DOCUMENT_MODELS


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    """Rôles des agents : l'administrateur attribue (ou change) le guichet de chacun."""

    list_display = ('agent', 'username', 'guichet', 'actif', 'created_at')
    list_editable = ('guichet',)
    list_filter = ('guichet', 'user__is_active')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at',)

    @admin.display(description=_('Agent'), ordering='user__last_name')
    def agent(self, obj):
        return obj.user.get_full_name() or obj.user.get_username()

    @admin.display(description=_("Nom d'utilisateur"), ordering='user__username')
    def username(self, obj):
        return obj.user.get_username()

    @admin.display(boolean=True, description=_('Actif'), ordering='user__is_active')
    def actif(self, obj):
        return obj.user.is_active


class DeletionFilter(admin.SimpleListFilter):
    title = 'suppression'
    parameter_name = 'suppression'

    def lookups(self, request, model_admin):
        return [('demandee', _('Demandée (à décider)')), ('supprime', _('Supprimé')), ('aucune', _('Aucune'))]

    def queryset(self, request, queryset):
        if self.value() == 'demandee':
            return queryset.filter(deletion_requested_at__isnull=False, deleted_at=None)
        if self.value() == 'supprime':
            return queryset.filter(deleted_at__isnull=False)
        if self.value() == 'aucune':
            return queryset.filter(deletion_requested_at=None, deleted_at=None)
        return queryset


class OfficialDocumentAdmin(admin.ModelAdmin):
    """
    Documents officiels des guichets : consultation, révocation, et décision sur les
    suppressions demandées par les agents (le contenu du document est scellé).
    """

    list_display = ('act_number', 'holder', 'status', 'suppression', 'envoye', 'created_by', 'created_at')
    list_filter = (DeletionFilter, 'status')
    date_hierarchy = 'created_at'
    actions = ['approve_deletion', 'reject_deletion', 'revoke']

    def get_search_fields(self, request):
        model = self.model
        text_fields = [
            name for name in model.SEALED_FIELDS
            if model._meta.get_field(name).get_internal_type() in ('CharField', 'TextField')
        ]
        return ['act_number', *text_fields]

    @admin.display(description=_('Titulaire / objet'))
    def holder(self, obj):
        return obj.holder_name

    @admin.display(boolean=True, description=_("Envoyé à l'usager"), ordering='sent_at')
    def envoye(self, obj):
        return obj.sent_at is not None

    @admin.display(description=_('Suppression'))
    def suppression(self, obj):
        if obj.deleted_at:
            return _('Supprimé le %(date)s') % {'date': f'{timezone.localtime(obj.deleted_at):%d/%m/%Y}'}
        if obj.deletion_pending:
            return _('Demandée : %(reason)s') % {'reason': obj.deletion_reason[:80]}
        return '—'

    def get_readonly_fields(self, request, obj=None):
        # Tout est en lecture seule sauf le statut (révocation).
        return [f.name for f in self.model._meta.fields if f.name != 'status']

    def has_add_permission(self, request):
        return False  # les documents sont établis par les agents, depuis leur guichet

    def has_delete_permission(self, request, obj=None):
        # Jamais d'effacement définitif : le numéro serait réattribué et la trace perdue.
        # Suppression = demande de l'agent acceptée (document masqué, conservé) ; sinon révocation.
        return False

    @admin.action(description=_("Accepter la suppression demandée par l'agent"))
    def approve_deletion(self, request, queryset):
        count = 0
        for act in queryset.filter(deletion_requested_at__isnull=False, deleted_at=None):
            act.deleted_at = timezone.now()
            act.deleted_by = request.user
            act.save(update_fields=['deleted_at', 'deleted_by'])
            count += 1
        self.message_user(request, _('%(count)s document(s) supprimé(s).') % {'count': count}, messages.SUCCESS)

    @admin.action(description=_("Refuser la suppression demandée par l'agent"))
    def reject_deletion(self, request, queryset):
        count = queryset.filter(deletion_requested_at__isnull=False, deleted_at=None).update(
            deletion_requested_at=None, deletion_requested_by=None, deletion_reason='',
        )
        self.message_user(request, _('%(count)s demande(s) de suppression refusée(s) : les documents sont conservés.') % {'count': count},
                          messages.SUCCESS)

    @admin.action(description=_('Révoquer les documents sélectionnés'))
    def revoke(self, request, queryset):
        count = queryset.exclude(status='REVOKED').update(status='REVOKED')
        self.message_user(request, _('%(count)s document(s) révoqué(s).') % {'count': count}, messages.SUCCESS)


for _model in DOCUMENT_MODELS:
    admin.site.register(_model, OfficialDocumentAdmin)
