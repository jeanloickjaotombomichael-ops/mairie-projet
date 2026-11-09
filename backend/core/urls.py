"""Routage principal du projet Mairy Project.

- /       : page d'accueil (bouton « Se connecter » vers /connexion/)
- /scanner/ : scan du QR code d'un bon de retrait (agents)
- /verifier/<id>/ : vérification d'un bon de retrait et remise du document (agents)
- /connexion/ : connexion commune (administrateurs → /admin/, agents → leur guichet)
- /agent/ : espace des agents municipaux (un guichet par agent)
- /admin/ : administration Django (administrateurs)
- /api/   : API JSON consommée par le frontend React
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from agents.views import ConnexionView, DeconnexionView, remettre_document, ticket_verify

from .views import LandingView, ScannerView

urlpatterns = [
    path('', LandingView.as_view(), name='home'),
    path('scanner/', ScannerView.as_view(), name='scanner'),
    # QR code du bon de retrait (réservé aux agents) et remise du document officiel.
    path('verifier/<uuid:token>/', ticket_verify, name='verifier'),
    path('verifier/<uuid:token>/remettre/', remettre_document, name='remettre_document'),
    path('connexion/', ConnexionView.as_view(), name='connexion'),
    path('deconnexion/', DeconnexionView.as_view(), name='deconnexion'),
    path('agent/', include('agents.urls')),
    # Changement de langue (formulaire du sélecteur, POST vers /i18n/setlang/).
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('api/', include('documents.urls')),
    path('api/', include('espace.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
