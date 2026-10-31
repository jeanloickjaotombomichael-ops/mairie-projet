"""Crée des documents de démonstration (idempotent) pour la soutenance.

Usage : python manage.py seed_demo
"""
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from documents.models import Document

DEMO_NAMESPACE = uuid.UUID('6f1d1f0e-8b5a-4c55-9a53-0d6c0a7b2f10')


def demo_id(slug):
    """UUID déterministe : relancer la commande ne duplique rien."""
    return uuid.uuid5(DEMO_NAMESPACE, f'mairie-verify/demo/{slug}')


class Command(BaseCommand):
    help = "Crée 4 documents de démonstration : valide, révoqué, expiré, falsifié."

    def handle(self, *args, **options):
        now = timezone.now()

        demos = [
            {
                'slug': 'valid',
                'label': 'VALIDE',
                'fields': {
                    'document_type': Document.DocumentType.BIRTH_CERTIFICATE,
                    'holder_first_name': 'Aina',
                    'holder_last_name': 'RAKOTOMALALA',
                    'holder_national_id': '101 234 567 890',
                    'issue_date': datetime(2026, 3, 12, 9, 30, 0, tzinfo=dt_timezone.utc),
                },
            },
            {
                'slug': 'revoked',
                'label': 'RÉVOQUÉ',
                'fields': {
                    'document_type': Document.DocumentType.MARRIAGE_CERTIFICATE,
                    'holder_first_name': 'Hery',
                    'holder_last_name': 'RANDRIANASOLO',
                    'holder_national_id': '',
                    'issue_date': datetime(2026, 4, 2, 10, 0, 0, tzinfo=dt_timezone.utc),
                },
                'after': {'status': Document.Status.REVOKED},
            },
            {
                'slug': 'expired',
                'label': 'EXPIRÉ',
                'fields': {
                    'document_type': Document.DocumentType.ATTESTATION,
                    'holder_first_name': 'Lalao',
                    'holder_last_name': 'RAVELOSON',
                    'holder_national_id': '',
                    'issue_date': datetime(2025, 1, 15, 8, 0, 0, tzinfo=dt_timezone.utc),
                    'expiry_date': now - timedelta(days=30),
                },
            },
            {
                'slug': 'tampered',
                'label': 'FALSIFIÉ',
                'fields': {
                    'document_type': Document.DocumentType.DIPLOMA,
                    'holder_first_name': 'Tiana',
                    'holder_last_name': 'ANDRIAMAHEFA',
                    'holder_national_id': '',
                    'issue_date': datetime(2026, 6, 20, 14, 45, 0, tzinfo=dt_timezone.utc),
                },
                # Modification directe en base, sans re-scellement : l'empreinte ne correspond plus.
                'after': {'holder_last_name': 'FALSIFIE'},
            },
        ]

        self.stdout.write(self.style.MIGRATE_HEADING('Documents de démonstration'))

        for demo in demos:
            pk = demo_id(demo['slug'])
            document = Document.all_objects.filter(pk=pk).first()
            created = False
            if document is None:
                document = Document(id=pk, **demo['fields'])
                document.save()  # scellement automatique à la création
                created = True

            after = demo.get('after')
            if after:
                Document.all_objects.filter(pk=pk).update(**after)

            state = 'créé' if created else 'déjà présent'
            self.stdout.write(f"\n[{demo['label']}] {state}")
            self.stdout.write(f'  UUID     : {pk}')
            self.stdout.write(f'  Frontend : {settings.FRONTEND_URL}/verifier/{pk}')
            self.stdout.write(f'  API      : /api/verify/{pk}/')

        self.stdout.write(self.style.SUCCESS('\nTerminé.'))
