"""Pages du projet hors API et hors administration."""
from django.utils.translation import gettext as _
from django.views.generic import TemplateView


class LandingView(TemplateView):
    """Page d'accueil du backend (http://localhost:8000/), avant la connexion."""

    template_name = 'landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fin de la phrase « Simple, sûr et rapide pour … », écrite lettre à lettre.
        context['typed_words'] = [
            _('les actes de naissance'),
            _('les actes de mariage'),
            _('les actes de décès'),
            _('les demandes des usagers'),
            _('les documents officiels'),
        ]
        return context
