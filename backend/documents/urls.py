from django.urls import path

from . import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('verify/<uuid:token>/', views.verify_document, name='verify_document'),
    path('agent-requests/', views.agent_request_create, name='agent_request_create'),
    path('documents/<uuid:token>/qr.png', views.document_qr, name='document_qr'),
    path('admin/fraud-scan/', views.fraud_scan, name='fraud_scan'),
    path('admin/stats/', views.admin_stats, name='admin_stats'),
]
