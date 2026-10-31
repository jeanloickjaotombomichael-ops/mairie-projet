"""Aiguillage automatique : chaque nouvelle demande d'usager est attribuée au guichet de son type."""
from django.db.models.signals import pre_save
from django.dispatch import receiver

from espace.models import DossierRequest

from .guichets import guichet_for_type


@receiver(pre_save, sender=DossierRequest)
def route_new_request(sender, instance, **kwargs):
    if instance._state.adding:
        number = guichet_for_type(instance.dossier_type)
        instance.guichet = str(number) if number else ''
