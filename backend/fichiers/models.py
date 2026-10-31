"""Dossiers personnels des agents : dossiers, fichiers importés, corbeille. Chacun ne voit que les siens."""
import os
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def _upload_to(instance, filename):
    # Nom aléatoire sur le disque (le nom d'origine est gardé dans `name`).
    extension = os.path.splitext(filename)[1].lower()[:10]
    return f'dossiers/{instance.owner_id}/{uuid.uuid4().hex}{extension}'


class Folder(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='folders', verbose_name=_('propriétaire'),
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name=_('dans'),
    )
    name = models.CharField(_('nom'), max_length=120)
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    trashed_at = models.DateTimeField(_('placé dans la corbeille le'), null=True, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('dossier')
        verbose_name_plural = _('dossiers')

    def __str__(self):
        return self.name

    def ancestors(self):
        """Dossiers parents, de la racine jusqu'à celui-ci compris (fil d'Ariane)."""
        chain, folder = [], self
        while folder is not None:
            chain.append(folder)
            folder = folder.parent
        return chain[::-1]

    def is_reachable(self):
        """Ni lui ni un de ses parents n'est dans la corbeille."""
        return all(folder.trashed_at is None for folder in self.ancestors())


class StoredFile(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stored_files', verbose_name=_('propriétaire'),
    )
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True, related_name='files', verbose_name=_('dossier'),
    )
    name = models.CharField(_('nom'), max_length=255)
    file = models.FileField(_('fichier'), upload_to=_upload_to)
    size = models.PositiveBigIntegerField(_('taille'), default=0)
    content_type = models.CharField(_('type'), max_length=120, blank=True)
    created_at = models.DateTimeField(_('importé le'), auto_now_add=True)
    trashed_at = models.DateTimeField(_('placé dans la corbeille le'), null=True, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('fichier')
        verbose_name_plural = _('fichiers')

    def __str__(self):
        return self.name

    @property
    def extension(self):
        return os.path.splitext(self.name)[1].lstrip('.').upper()[:5] or '—'

    def is_reachable(self):
        return self.trashed_at is None and (self.folder is None or self.folder.is_reachable())


def trash_count(user):
    """Éléments dans la corbeille (badge du menu latéral)."""
    return (Folder.objects.filter(owner=user).exclude(trashed_at=None).count()
            + StoredFile.objects.filter(owner=user).exclude(trashed_at=None).count())
