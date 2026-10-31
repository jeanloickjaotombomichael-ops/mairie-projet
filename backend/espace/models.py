"""Modèles de l'espace usager : demandes de dossiers et messages de contact."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class DossierRequest(models.Model):
    """Demande de dossier déposée par un usager connecté (identifié par Clerk)."""

    class DossierType(models.TextChoices):
        RECETTE = 'recette', _('Recette')
        TRANSPORT = 'transport', _('Transport')
        URBANISME = 'urbanisme', _('Urbanisme')
        MARCHE = 'marche', _('Marché')
        CADASTRE = 'cadastre', _('Cadastre')
        IMPOT_FONCIER = 'impot_foncier', _('Impôt foncier')
        NAISSANCE = 'naissance', _('Acte de naissance')
        MARIAGE = 'mariage', _('Acte de mariage')
        DECES = 'deces', _('Acte de décès')
        LEGISLATION = 'legislation', _('Législation')
        ACTES_DIVERS = 'actes_divers', _('Actes divers')
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        IN_PROGRESS = 'IN_PROGRESS', _('En cours de traitement')
        APPROVED = 'APPROVED', _('Approuvée')
        REJECTED = 'REJECTED', _('Refusée')
        COMPLETED = 'COMPLETED', _('Terminée')
    clerk_user_id = models.CharField(_('identifiant Clerk'), max_length=100, db_index=True)
    dossier_type = models.CharField(_('type de dossier'), max_length=20, choices=DossierType.choices)
    guichet = models.CharField(_('guichet'), max_length=3, blank=True)
    status = models.CharField(_('statut'), max_length=15, choices=Status.choices, default=Status.PENDING)
    # Renseignée juste après la création (MV-<année>-<id sur 6 chiffres>).
    # NULL (et non '') tant qu'elle n'existe pas : l'unicité ignore les NULL.
    reference = models.CharField(_('référence'), max_length=20, unique=True, null=True, blank=True)
    identity = models.JSONField(_('identité du demandeur'), default=dict)
    details = models.JSONField(_('détails de la demande'), default=dict)
    response_message = models.TextField(_('réponse de la mairie'), blank=True)
    responded_at = models.DateTimeField(_('date de la réponse'), null=True, blank=True)
    response_read = models.BooleanField(_('réponse lue'), default=False)
    created_at = models.DateTimeField(_('créée le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('modifiée le'), auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('demande de dossier')
        verbose_name_plural = _('demandes de dossiers')
        indexes = [
            models.Index(fields=['clerk_user_id', '-created_at'], name='espace_dossier_user_idx'),
        ]

    def __str__(self):
        return f'{self.reference or self.pk} — {self.get_dossier_type_display()}'

    def save(self, *args, **kwargs):
        creating = self.pk is None
        update_fields = kwargs.get('update_fields')

        # Une nouvelle réponse (ou une réponse modifiée) repasse en « non lue ».
        previous = ''
        if not creating:
            previous = (
                type(self).objects.filter(pk=self.pk).values_list('response_message', flat=True).first()
                or ''
            )
        current = self.response_message or ''
        if current != previous:
            if current.strip():
                self.responded_at = timezone.now()
                self.response_read = False
            else:
                self.responded_at = None
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'responded_at', 'response_read'}

        super().save(*args, **kwargs)

        if creating and not self.reference:
            year = timezone.localtime(self.created_at).year
            self.reference = f'MV-{year}-{self.pk:06d}'
            super().save(update_fields=['reference'])


class ContactMessage(models.Model):
    """Message envoyé depuis la page publique « Contact »."""

    first_name = models.CharField(_('prénom'), max_length=100)
    last_name = models.CharField(_('nom'), max_length=100, blank=True)
    phone = models.CharField(_('téléphone'), max_length=30)
    email = models.EmailField(_('e-mail'))
    message = models.TextField(_('message'), blank=True)
    handled = models.BooleanField(_('traité'), default=False)
    created_at = models.DateTimeField(_('reçu le'), auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('message de contact')
        verbose_name_plural = _('messages de contact')

    def __str__(self):
        return f'{self.first_name} {self.last_name}'.strip() + f' — {self.email}'


class EspaceVisitor(models.Model):
    """Usager (compte Clerk) qui utilise l'espace : dernière activité, pour la page « Mail » de l'admin."""

    clerk_user_id = models.CharField(_('identifiant Clerk'), max_length=100, unique=True)
    first_seen = models.DateTimeField(_('première visite'), auto_now_add=True)
    last_seen = models.DateTimeField(_('dernière activité'), db_index=True)

    class Meta:
        ordering = ['-last_seen']
        verbose_name = _("usager de l'espace")
        verbose_name_plural = _("usagers de l'espace")

    def __str__(self):
        return self.clerk_user_id

    @classmethod
    def record(cls, clerk_user_id):
        """Note l'activité de l'usager (au plus une écriture par minute)."""
        now = timezone.now()
        updated = cls.objects.filter(
            clerk_user_id=clerk_user_id, last_seen__lt=now - timezone.timedelta(minutes=1),
        ).update(last_seen=now)
        if not updated:
            cls.objects.get_or_create(clerk_user_id=clerk_user_id, defaults={'last_seen': now})
