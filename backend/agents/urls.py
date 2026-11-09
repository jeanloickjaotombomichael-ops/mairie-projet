from django.urls import path
from django.views.generic import RedirectView

from fichiers import views as fichiers_views

from . import views

app_name = 'agents'

urlpatterns = [
    path('', views.agent_home, name='home'),
    path('inscription/', views.inscription, name='inscription'),
    path('parametres/', views.agent_settings, name='settings'),
    # Ancienne adresse de la page « Mot de passe » (favoris des agents).
    path('mot-de-passe/', RedirectView.as_view(pattern_name='agents:settings')),
    path('assistant/', views.assistant, name='assistant'),
    path('guichet-<int:number>/', views.guichet_dashboard, name='dashboard'),
    path('guichet-<int:number>/demandes/', views.guichet_requests, name='requests'),
    path('guichet-<int:number>/demandes/<int:pk>/', views.guichet_request_detail, name='request_detail'),
    path('guichet-<int:number>/recherche/', views.agent_search, name='search'),
    path('guichet-<int:number>/documents/', views.documents_home, name='documents'),
    path('guichet-<int:number>/documents/nouveau/', views.document_create, name='document_create'),
    path('guichet-<int:number>/documents/<uuid:pk>/', views.document_detail, name='document_detail'),
    path('guichet-<int:number>/documents/<uuid:pk>/pdf/', views.document_pdf, name='document_pdf'),
    path('guichet-<int:number>/documents/<uuid:pk>/bon/', views.document_ticket, name='document_ticket'),
    path('guichet-<int:number>/documents/<uuid:pk>/envoyer/', views.document_send, name='document_send'),
    path('guichet-<int:number>/documents/<uuid:pk>/supprimer/', views.document_delete, name='document_delete'),
    path('guichet-<int:number>/documents/<uuid:pk>/supprimer/annuler/', views.document_cancel_deletion,
         name='document_cancel_deletion'),
    path('guichet-<int:number>/notifications/', views.guichet_notifications, name='notifications'),
    path('guichet-<int:number>/notifications/compteur/', views.notifications_count, name='notifications_count'),
    path('guichet-<int:number>/mail/', views.guichet_mail, name='mail'),
    path('guichet-<int:number>/messages/', views.guichet_messages, name='messages'),
    path('guichet-<int:number>/dossiers/', fichiers_views.folders, name='folders'),
    path('guichet-<int:number>/dossiers/documents/', views.documents_list, name='folder_documents'),
    path('guichet-<int:number>/dossiers/fichier/<int:pk>/', fichiers_views.file_open, name='file_open'),
    path('guichet-<int:number>/corbeille/', fichiers_views.trash, name='trash'),
]
