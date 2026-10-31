from django.urls import path

from . import views

urlpatterns = [
    path('dossiers/', views.dossier_collection, name='dossier_collection'),
    # « read-all » doit précéder « <id>/read » (même préfixe).
    path('dossiers/read-all/', views.dossier_read_all, name='dossier_read_all'),
    path('dossiers/<int:pk>/read/', views.dossier_mark_read, name='dossier_mark_read'),
    path('dossiers/<int:pk>/documents/<uuid:document_id>/', views.dossier_document, name='dossier_document'),
    path('contact/', views.contact_create, name='contact_create'),
    path('mails/', views.mail_collection, name='mail_collection'),
    path('mails/<int:pk>/read/', views.mail_mark_read, name='mail_mark_read'),
    path('assistant/', views.assistant, name='espace_assistant'),
]
