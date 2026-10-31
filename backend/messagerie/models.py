"""Boîte mail des administrateurs et des agents (à la manière de Gmail) : un exemplaire par propriétaire."""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Label(models.Model):
    """Libellé créé par un utilisateur pour classer ses messages."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mail_labels', verbose_name=_('propriétaire'),
    )
    name = models.CharField(_('nom'), max_length=60)

    class Meta:
        ordering = ['name']
        unique_together = [('owner', 'name')]
        verbose_name = _('libellé')
        verbose_name_plural = _('libellés')

    def __str__(self):
        return self.name


class Mail(models.Model):
    """
    Un message dans la boîte d'un utilisateur. L'envoi crée un exemplaire « envoyé » chez l'expéditeur
    et un exemplaire « reçu » chez chaque destinataire qui a un compte (équipe) ; les autres adresses
    reçoivent un vrai e-mail.
    """

    class Folder(models.TextChoices):
        INBOX = 'INBOX', _('Reçu')
        SENT = 'SENT', _('Envoyé')
        DRAFT = 'DRAFT', _('Brouillon')

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mails', verbose_name=_('propriétaire'),
        null=True, blank=True,
    )
    citizen_id = models.CharField(_('usager (identifiant Clerk)'), max_length=100, blank=True, db_index=True)
    service = models.CharField(_('guichet ou service'), max_length=10, blank=True)
    folder = models.CharField(_('dossier'), max_length=5, choices=Folder.choices, default=Folder.INBOX)
    sender_name = models.CharField(_("nom de l'expéditeur"), max_length=150, blank=True)
    sender_email = models.EmailField(_("e-mail de l'expéditeur"), blank=True)
    to = models.CharField(_('destinataires'), max_length=1000, blank=True)
    subject = models.CharField(_('objet'), max_length=255, blank=True)
    body = models.TextField(_('message'), blank=True)
    created_at = models.DateTimeField(_('date'), default=timezone.now)

    is_read = models.BooleanField(_('lu'), default=True)
    is_starred = models.BooleanField(_('suivi'), default=False)
    is_important = models.BooleanField(_('important'), default=False)
    snoozed_until = models.DateTimeField(_("en attente jusqu'au"), null=True, blank=True)
    trashed_at = models.DateTimeField(_('placé dans la corbeille le'), null=True, blank=True)
    labels = models.ManyToManyField(Label, blank=True, related_name='mails', verbose_name=_('libellés'))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('message')
        verbose_name_plural = _('messages')

    def __str__(self):
        return self.subject or str(_('(aucun objet)'))
