"""Attribue leur guichet aux demandes déposées avant l'aiguillage automatique."""
from django.db import migrations


def route_existing(apps, schema_editor):
    from agents.guichets import guichet_for_type

    DossierRequest = apps.get_model('espace', 'DossierRequest')
    for dossier in DossierRequest.objects.exclude(guichet__in=['1', '2', '3', '4', '5']):
        number = guichet_for_type(dossier.dossier_type)
        if number:
            DossierRequest.objects.filter(pk=dossier.pk).update(guichet=str(number))


class Migration(migrations.Migration):
    dependencies = [
        ('agents', '0004_agentprofile_notifications_seen_at_and_more'),
        ('espace', '0001_initial'),
    ]

    operations = [migrations.RunPython(route_existing, migrations.RunPython.noop)]
