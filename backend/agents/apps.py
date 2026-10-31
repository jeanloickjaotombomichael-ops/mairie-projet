from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agents'
    verbose_name = _('Agents municipaux')

    def ready(self):
        from . import signals  # noqa: F401 (branche l'aiguillage des demandes vers les guichets)
