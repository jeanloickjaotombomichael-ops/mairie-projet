from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from agents.labels import field_label, option_label

from .models import ContactMessage, DossierRequest


@admin.register(DossierRequest)
class DossierRequestAdmin(admin.ModelAdmin):
    """Traitement des demandes : changer le statut et répondre à l'usager."""

    list_display = ('reference', 'demandeur', 'dossier_type', 'guichet', 'status', 'created_at', 'repondu')
    list_filter = ('status', 'dossier_type')
    search_fields = (
        'reference',
        'clerk_user_id',
        'identity__last_name',
        'identity__first_name',
        'identity__email',
        'identity__phone',
    )
    date_hierarchy = 'created_at'
    actions = ['mark_in_progress', 'mark_approved', 'mark_rejected', 'mark_completed']
    readonly_fields = (
        'reference',
        'clerk_user_id',
        'dossier_type',
        'guichet',
        'identity_display',
        'details_display',
        'created_at',
        'updated_at',
        'responded_at',
        'response_read',
    )
    fieldsets = (
        (_('Demande'), {'fields': ('reference', 'dossier_type', 'guichet', 'clerk_user_id', 'created_at', 'updated_at')}),
        (_('Demandeur et contenu'), {'fields': ('identity_display', 'details_display')}),
        (_('Traitement'), {'fields': ('status', 'response_message', 'responded_at', 'response_read')}),
    )

    @staticmethod
    def _key_values(values):
        """Dictionnaire JSON → liste « libellé : valeur » lisible."""
        rows = [
            (field_label(key), option_label(value) if isinstance(value, str) else value)
            for key, value in (values or {}).items() if value not in (None, '')
        ]
        if not rows:
            return '—'
        return format_html('<dl class="mairy-kv">{}</dl>', format_html_join('', '<dt>{}</dt><dd>{}</dd>', rows))

    @admin.display(description=_('Identité du demandeur'))
    def identity_display(self, obj):
        return self._key_values(obj.identity)

    @admin.display(description=_('Détails de la demande'))
    def details_display(self, obj):
        return self._key_values(obj.details)

    @admin.display(description=_('Demandeur'))
    def demandeur(self, obj):
        identity = obj.identity or {}
        return f"{identity.get('last_name', '')} {identity.get('first_name', '')}".strip() or '—'

    @admin.display(boolean=True, description=_('Répondu'))
    def repondu(self, obj):
        return bool(obj.response_message)

    def has_add_permission(self, request):
        # Les demandes sont déposées par les usagers via l'API.
        return False

    def _set_status(self, request, queryset, status, label):
        updated = queryset.update(status=status, updated_at=timezone.now())
        self.message_user(request, _('%(count)s demande(s) marquée(s) « %(status)s ».') % {'count': updated, 'status': label}, messages.SUCCESS)

    @admin.action(description=_('Marquer comme « En cours de traitement »'))
    def mark_in_progress(self, request, queryset):
        self._set_status(request, queryset, DossierRequest.Status.IN_PROGRESS, _('En cours de traitement'))

    @admin.action(description=_('Marquer comme « Approuvée »'))
    def mark_approved(self, request, queryset):
        self._set_status(request, queryset, DossierRequest.Status.APPROVED, _('Approuvée'))

    @admin.action(description=_('Marquer comme « Refusée »'))
    def mark_rejected(self, request, queryset):
        self._set_status(request, queryset, DossierRequest.Status.REJECTED, _('Refusée'))

    @admin.action(description=_('Marquer comme « Terminée »'))
    def mark_completed(self, request, queryset):
        self._set_status(request, queryset, DossierRequest.Status.COMPLETED, _('Terminée'))


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """Messages reçus depuis la page Contact (consultation seule)."""

    list_display = ('created_at', 'first_name', 'last_name', 'email', 'phone', 'handled')
    list_filter = ('handled',)
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'message')
    date_hierarchy = 'created_at'
    actions = ['mark_handled']
    readonly_fields = ('first_name', 'last_name', 'phone', 'email', 'message', 'handled', 'created_at')

    def has_add_permission(self, request):
        return False

    @admin.action(description=_('Marquer comme traité'))
    def mark_handled(self, request, queryset):
        updated = queryset.update(handled=True)
        self.message_user(request, _('%(count)s message(s) marqué(s) comme traité(s).') % {'count': updated}, messages.SUCCESS)
