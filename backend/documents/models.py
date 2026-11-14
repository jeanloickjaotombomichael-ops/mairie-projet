
import hashlib
import hmac
import json
import uuid
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from agents.guichets import GUICHET_CHOICES


class ActiveDocumentManager(models.Manager):
    """Manager par défaut : exclut les documents supprimés (soft-delete)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Document(models.Model):
    class DocumentType(models.TextChoices):
        BIRTH_CERTIFICATE = 'BIRTH_CERTIFICATE', _('Acte de naissance')
        MARRIAGE_CERTIFICATE = 'MARRIAGE_CERTIFICATE', _('Acte de mariage')
        DEATH_CERTIFICATE = 'DEATH_CERTIFICATE', _('Acte de décès')
        DIPLOMA = 'DIPLOMA', _('Diplôme')
        ATTESTATION = 'ATTESTATION', _('Attestation')
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Actif')
        REVOKED = 'REVOKED', _('Révoqué')
        EXPIRED = 'EXPIRED', _('Expiré')
    # Résultats possibles de verify_authenticity()
    RESULT_VALID = 'VALID'
    RESULT_REVOKED = 'REVOKED'
    RESULT_EXPIRED = 'EXPIRED'
    RESULT_INVALID = 'INVALID'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.CharField(_('type de document'), max_length=30, choices=DocumentType.choices)
    holder_first_name = models.CharField(_('prénom du titulaire'), max_length=100)
    holder_last_name = models.CharField(_('nom du titulaire'), max_length=100)
    holder_national_id = models.CharField(
        _('numéro de CIN'), max_length=50, blank=True, default='',
        help_text=_('Optionnel.'),
    )
    holder_photo = models.ImageField(_('photo du titulaire'), upload_to='holders/', blank=True, null=True)
    issue_date = models.DateTimeField(_("date d'émission"), default=timezone.now)
    expiry_date = models.DateTimeField(_("date d'expiration"), blank=True, null=True)
    pdf_file = models.FileField(_('PDF officiel'), upload_to='documents/pdf/', blank=True, null=True)

    content_hash = models.CharField(_('empreinte SHA-256'), max_length=64, blank=True, editable=False)
    signature = models.CharField(_('signature HMAC-SHA256'), max_length=64, blank=True, editable=False)

    status = models.CharField(_('statut'), max_length=10, choices=Status.choices, default=Status.ACTIVE)

    is_deleted = models.BooleanField(_('supprimé'), default=False)
    deleted_at = models.DateTimeField(_('supprimé le'), blank=True, null=True)
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)

    # Le premier manager déclaré est le manager par défaut.
    objects = ActiveDocumentManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-issue_date']
        verbose_name = _('document')
        verbose_name_plural = _('documents')

    def __str__(self):
        return f'{self.get_document_type_display()} — {self.holder_first_name} {self.holder_last_name}'

    # ------------------------------------------------------------------
    # Scellement et vérification
    # ------------------------------------------------------------------
    def _issue_date_utc(self):
        issue = self.issue_date
        if timezone.is_naive(issue):
            issue = timezone.make_aware(issue, dt_timezone.utc)
        return issue.astimezone(dt_timezone.utc).replace(microsecond=0)

    def canonical_payload(self):
        """Représentation canonique et stable des champs d'identité."""
        data = {
            'id': str(self.id),
            'document_type': self.document_type,
            'holder_first_name': self.holder_first_name,
            'holder_last_name': self.holder_last_name,
            'holder_national_id': self.holder_national_id or '',
            'issue_date': self._issue_date_utc().strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

    def compute_hash(self):
        return hashlib.sha256(self.canonical_payload().encode('utf-8')).hexdigest()

    @staticmethod
    def compute_signature(content_hash):
        key = settings.DOCUMENT_SIGNING_KEY.encode('utf-8')
        return hmac.new(key, (content_hash or '').encode('utf-8'), hashlib.sha256).hexdigest()

    def seal(self):
        """Calcule et fige l'empreinte et la signature (à la création uniquement)."""
        self.issue_date = self._issue_date_utc()  # tronqué à la seconde, en UTC
        self.content_hash = self.compute_hash()
        self.signature = self.compute_signature(self.content_hash)

    def save(self, *args, **kwargs):
        if self._state.adding and not self.content_hash:
            self.seal()
        super().save(*args, **kwargs)

    def verify_authenticity(self):
        """Retourne is_authentic / hash_matches / signature_valid / status."""
        stored_hash = self.content_hash or ''
        stored_signature = self.signature or ''

        hash_matches = hmac.compare_digest(
            self.compute_hash().encode('utf-8'), stored_hash.encode('utf-8')
        )
        signature_valid = hmac.compare_digest(
            self.compute_signature(stored_hash).encode('utf-8'), stored_signature.encode('utf-8')
        )

        if self.is_deleted or self.status == self.Status.REVOKED:
            status = self.RESULT_REVOKED
        elif self.status == self.Status.EXPIRED or (
            self.expiry_date is not None and self.expiry_date <= timezone.now()
        ):
            status = self.RESULT_EXPIRED
        elif not (hash_matches and signature_valid):
            status = self.RESULT_INVALID
        else:
            status = self.RESULT_VALID

        return {
            'is_authentic': status == self.RESULT_VALID,
            'hash_matches': hash_matches,
            'signature_valid': signature_valid,
            'status': status,
        }

    @property
    def verification_url(self):
        return f'{settings.FRONTEND_URL}/verifier/{self.id}'

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])


class DocumentAuditLog(models.Model):
    class Action(models.TextChoices):
        VERIFIED_SUCCESS = 'VERIFIED_SUCCESS', _('Vérification réussie')
        VERIFIED_FRAUD = 'VERIFIED_FRAUD', _('Vérification échouée / fraude')
        REVOKED = 'REVOKED', _('Document révoqué')
        DELETED = 'DELETED', _('Document supprimé')
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs',
        verbose_name=_('document'),
    )
    action = models.CharField(_('action'), max_length=30, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('effectuée par'),
    )
    ip_address = models.GenericIPAddressField(_('adresse IP'), null=True, blank=True)
    details = models.TextField(_('détails'), blank=True)
    timestamp = models.DateTimeField(_('date'), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _("entrée du journal d'audit")
        verbose_name_plural = _("journal d'audit")

    def __str__(self):
        return f'{self.get_action_display()} — {self.timestamp:%Y-%m-%d %H:%M}'


class AgentAccessRequest(models.Model):
    REQUEST_TYPE_CHOICES = [
        ('AGENT_ACCESS', _('Agent Municipal — Création de documents administratifs')),
    ]

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        APPROVED = 'APPROVED', _('Approuvée')
        REJECTED = 'REJECTED', _('Rejetée')
    first_name = models.CharField(_('prénom'), max_length=100)
    last_name = models.CharField(_('nom'), max_length=100)
    phone_number = models.CharField(_('téléphone'), max_length=30, blank=True)
    email = models.EmailField(_('e-mail'))
    request_type = models.CharField(_('type de demande'), max_length=30, choices=REQUEST_TYPE_CHOICES)
    guichet = models.PositiveSmallIntegerField(
        _('guichet'), choices=GUICHET_CHOICES, null=True, blank=True,
        help_text=_("Guichet souhaité par le demandeur ; l'administrateur peut le changer avant d'approuver."),
    )
    message = models.TextField(_('précisions'), blank=True)
    status = models.CharField(_('statut'), max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(_('reçue le'), auto_now_add=True)
    reviewed_at = models.DateTimeField(_('traitée le'), blank=True, null=True)
    # Mot de passe choisi à l'inscription (haché) ; copié sur le compte à l'approbation puis effacé.
    password_hash = models.CharField(_('mot de passe (haché)'), max_length=128, blank=True, editable=False)
    agent_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='agent_access_request', verbose_name=_('compte agent créé'),
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("demande d'accès agent")
        verbose_name_plural = _("demandes d'accès agent")

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.get_status_display()})'
