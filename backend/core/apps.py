from django.contrib.admin.apps import AdminConfig


class MairyAdminConfig(AdminConfig):
    """Remplace le site d'administration par défaut par le tableau de bord Mairy."""

    default_site = 'core.admin_site.MairyAdminSite'
