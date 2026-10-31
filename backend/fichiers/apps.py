from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FichiersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fichiers'
    verbose_name = _('Dossiers des agents')

    def ready(self):
        from django.db.models.signals import post_delete

        from .models import StoredFile

        # Suppression définitive : le fichier quitte aussi le disque.
        post_delete.connect(
            lambda instance, **kwargs: instance.file.delete(save=False), sender=StoredFile, weak=False,
        )
