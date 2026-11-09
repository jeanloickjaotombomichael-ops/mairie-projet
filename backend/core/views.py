"""Pages du projet hors API et hors administration."""
from django.utils.translation import gettext as _
from django.contrib.auth.mixins import LoginRequiredMixin
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


class ScannerView(LoginRequiredMixin, TemplateView):
    """Scan du QR code d'un bon de retrait (agents) : ouvre la page /verifier/… du bon."""

    template_name = 'scanner.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['scan_messages'] = {
            'start': _('Activer la caméra'),
            'stop': _('Arrêter la caméra'),
            'starting': _('Démarrage de la caméra…'),
            'denied': _("L'accès à la caméra a été refusé. Autorisez-le dans votre navigateur, ou saisissez l'identifiant ci-dessous."),
            'error': _("Impossible de démarrer la caméra sur cet appareil. Saisissez l'identifiant ci-dessous."),
            'insecure': _('La caméra nécessite une connexion sécurisée (HTTPS) ou localhost.'),
            'unrecognized': _("QR code non reconnu : il ne contient pas d'identifiant de document."),
        }
        return context
