import json
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AgentAccessRequest, Document, DocumentAuditLog

User = get_user_model()


class BaseTestCase(TestCase):
    def setUp(self):
        cache.clear()  # remet à zéro la limitation de débit

    def make_document(self, **overrides):
        fields = {
            'document_type': Document.DocumentType.BIRTH_CERTIFICATE,
            'holder_first_name': 'Aina',
            'holder_last_name': 'RAKOTO',
            'holder_national_id': '101 234 567 890',
            'issue_date': timezone.now(),
        }
        fields.update(overrides)
        return Document.objects.create(**fields)

    def verify(self, token):
        return self.client.get(reverse('verify_document', args=[token]))


class HealthTests(BaseTestCase):
    def test_health(self):
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})


class VerifyTests(BaseTestCase):
    def test_valid_document(self):
        document = self.make_document()
        response = self.verify(document.id)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_authentic'])
        self.assertEqual(data['status'], 'VALID')
        self.assertTrue(data['hash_matches'])
        self.assertTrue(data['signature_valid'])
        self.assertIsNotNone(data['document'])
        self.assertEqual(data['document']['holder_last_name'], 'RAKOTO')
        self.assertEqual(data['document']['document_type_label'], 'Acte de naissance')
        self.assertEqual(data['document']['signature_fingerprint'], document.content_hash)
        self.assertIsNone(data['document']['holder_photo_url'])
        self.assertIsNone(data['document']['pdf_url'])
        log = DocumentAuditLog.objects.get()
        self.assertEqual(log.action, DocumentAuditLog.Action.VERIFIED_SUCCESS)

    def test_tampered_document(self):
        document = self.make_document()
        Document.all_objects.filter(pk=document.pk).update(holder_last_name='FALSIFIE')
        data = self.verify(document.id).json()
        self.assertFalse(data['is_authentic'])
        self.assertEqual(data['status'], 'INVALID')
        self.assertFalse(data['hash_matches'])
        self.assertIsNone(data['document'])
        log = DocumentAuditLog.objects.get()
        self.assertEqual(log.action, DocumentAuditLog.Action.VERIFIED_FRAUD)

    def test_forged_signature(self):
        document = self.make_document()
        Document.all_objects.filter(pk=document.pk).update(signature='0' * 64)
        data = self.verify(document.id).json()
        self.assertFalse(data['is_authentic'])
        self.assertTrue(data['hash_matches'])
        self.assertFalse(data['signature_valid'])
        self.assertEqual(data['status'], 'INVALID')

    def test_revoked_document(self):
        document = self.make_document(status=Document.Status.REVOKED)
        data = self.verify(document.id).json()
        self.assertFalse(data['is_authentic'])
        self.assertEqual(data['status'], 'REVOKED')
        self.assertIsNone(data['document'])

    def test_expired_document(self):
        document = self.make_document(expiry_date=timezone.now() - timedelta(days=1))
        data = self.verify(document.id).json()
        self.assertFalse(data['is_authentic'])
        self.assertEqual(data['status'], 'EXPIRED')
        self.assertIsNone(data['document'])

    def test_unknown_uuid(self):
        response = self.verify('11111111-1111-4111-8111-111111111111')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'detail': 'not_found'})
        log = DocumentAuditLog.objects.get()
        self.assertIsNone(log.document)
        self.assertEqual(log.action, DocumentAuditLog.Action.VERIFIED_FRAUD)

    def test_soft_deleted_document_is_not_found(self):
        document = self.make_document()
        document.soft_delete()
        self.assertEqual(self.verify(document.id).status_code, 404)


class ScannerPageTests(BaseTestCase):
    def test_landing_links_to_scanner(self):
        self.assertContains(self.client.get(reverse('home')), reverse('scanner'))

    def test_scanner_is_public_and_targets_the_verification_api(self):
        response = self.client.get(reverse('scanner'))
        self.assertContains(response, 'html5-qrcode.min.js')
        self.assertContains(response, reverse('verify_document', args=['00000000-0000-0000-0000-000000000000']))


class AgentRequestTests(BaseTestCase):
    url_name = 'agent_request_create'

    def payload(self, **overrides):
        data = {
            'first_name': 'Jean',
            'last_name': 'RABE',
            'phone_number': '+261 34 00 000 00',
            'email': 'jean@example.com',
            'request_type': 'AGENT_ACCESS',
            'message': 'Bonjour',
        }
        data.update(overrides)
        return data

    def post(self, data):
        return self.client.post(
            reverse(self.url_name), data=json.dumps(data), content_type='application/json'
        )

    def test_create(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(AgentAccessRequest.objects.count(), 1)
        created = AgentAccessRequest.objects.get()
        self.assertEqual(response.json(), {'id': created.id})
        self.assertEqual(created.status, AgentAccessRequest.Status.PENDING)
        self.assertIsNone(created.guichet)  # attribué par l'administrateur

    def test_message_is_optional(self):
        data = self.payload()
        del data['message']
        self.assertEqual(self.post(data).status_code, 201)

    def test_validation_errors(self):
        response = self.post(self.payload(email='pas-un-email', first_name='', request_type='NOPE'))
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertIn('email', errors)
        self.assertIn('first_name', errors)
        self.assertIn('request_type', errors)
        self.assertEqual(AgentAccessRequest.objects.count(), 0)

    def test_invalid_json(self):
        response = self.client.post(
            reverse(self.url_name), data='pas du json', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json())

    @override_settings(AGENT_REQUEST_RATE_LIMIT=(2, 60))
    def test_rate_limit(self):
        self.assertEqual(self.post(self.payload()).status_code, 201)
        self.assertEqual(self.post(self.payload()).status_code, 201)
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {'detail': 'throttled'})


class QrTests(BaseTestCase):
    def test_qr_png(self):
        document = self.make_document()
        response = self.client.get(reverse('document_qr', args=[document.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG'))

    def test_qr_unknown(self):
        response = self.client.get(
            reverse('document_qr', args=['11111111-1111-4111-8111-111111111111'])
        )
        self.assertEqual(response.status_code, 404)


class AdminEndpointTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.regular = User.objects.create_user('regular', password='x-pass-12345')
        self.staff = User.objects.create_user('staff', password='x-pass-12345', is_staff=True)

    def test_stats_anonymous(self):
        response = self.client.get(reverse('admin_stats'))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_stats_non_staff(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(reverse('admin_stats')).status_code, 403)

    def test_stats_staff(self):
        self.make_document()
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin_stats'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(sum(data['totals']), 1)
        self.assertEqual(len(data['months']), len(data['totals']))

    def test_fraud_scan_anonymous(self):
        self.assertEqual(self.client.post(reverse('fraud_scan')).status_code, 401)

    def test_fraud_scan_non_staff(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.post(reverse('fraud_scan')).status_code, 403)

    def test_fraud_scan_missing_file(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('fraud_scan'))
        self.assertEqual(response.status_code, 400)

    def test_fraud_scan_no_uuid(self):
        self.client.force_login(self.staff)
        upload = SimpleUploadedFile('vide.txt', b'rien')
        response = self.client.post(reverse('fraud_scan'), {'target_file': upload})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], 'no_uuid_found')

    def test_fraud_scan_known_document(self):
        document = self.make_document()
        self.client.force_login(self.staff)
        upload = SimpleUploadedFile('scan.pdf', b'%PDF-')
        with mock.patch('documents.views.extract_uuid_from_file', return_value=document.id):
            response = self.client.post(reverse('fraud_scan'), {'target_file': upload})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_authentic'])
        self.assertEqual(data['filename'], 'scan.pdf')
        self.assertTrue(data['found'])

    def test_fraud_scan_unknown_document(self):
        self.client.force_login(self.staff)
        upload = SimpleUploadedFile('scan.pdf', b'%PDF-')
        unknown = '11111111-1111-4111-8111-111111111111'
        with mock.patch('documents.views.extract_uuid_from_file', return_value=uuid.UUID(unknown)):
            response = self.client.post(reverse('fraud_scan'), {'target_file': upload})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['is_authentic'])
        self.assertFalse(data['found'])
        self.assertEqual(data['id'], unknown)
