"""Tests de l'espace usager (sans réseau : l'authentification Clerk est simulée)."""
import base64
import json
import re
import time
import types
from datetime import timedelta
from unittest import mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import auth
from .auth import AuthNotConfigured, InvalidToken
from .models import ContactMessage, DossierRequest
from .schemas import DETAIL_FIELDS

ISSUER = 'https://clerk.example.test'

CLERK_SETTINGS = {
    'CLERK_ISSUER': ISSUER,
    'CLERK_PUBLISHABLE_KEY': '',
    'CLERK_JWKS_URL': '',
    'CLERK_AUTHORIZED_PARTIES': [],
}

IDENTITY = {
    'last_name': 'RAKOTO',
    'first_name': 'Aina',
    'email': 'aina@example.com',
    'phone': '+261 34 00 000 00',
    'national_id': '101 234 567 890',
    'address': 'Mahabibo, Mahajanga',
}

# Étape « Quartier » des demandes d'actes (naissance, mariage, décès, législation).
QUARTIER = {'fokontany': 'Mahabibo', 'main_residence': 'oui'}

VALID_DETAILS = {
    'naissance': {
        'concerned_last_name': 'RAKOTO',
        'concerned_first_name': 'Hery',
        'birth_date': '2001-05-17',
        'birth_place': 'Mahajanga',
        'father_name': 'Jean',
        'mother_name': 'Marie',
        'copies': '2',
        **QUARTIER,
    },
    'mariage': {
        'spouse1_name': 'Jean RAKOTO',
        'spouse2_name': 'Marie RABE',
        'marriage_date': '2015-08-01',
        'marriage_place': 'Mahajanga',
        'copies': '1',
        **QUARTIER,
    },
    'deces': {
        'deceased_name': 'Paul RAKOTO',
        'death_date': '2020-01-31',
        'death_place': 'Mahajanga',
        'relationship': 'child',
        'copies': '1',
        **QUARTIER,
    },
    'legislation': {'text_type': 'arrete', 'reference_number': '12/2024', 'subject': 'Circulation', **QUARTIER},
    'actes_divers': {'act_nature': 'Attestation', 'description': 'Attestation de résidence', 'copies': '1'},
    'recette': {'payment_type': 'patente', 'reference_number': 'P-1', 'amount': '12500,50', 'period': '2024'},
    'urbanisme': {
        'request_kind': 'permis_construire',
        'plot_address': 'Rue 1, Mahabibo',
        'works_description': 'Construction d\'une maison',
        'surface': '120',
        'cadastral_reference': 'C-12',
    },
    'transport': {
        'request_kind': 'licence',
        'vehicle_type': 'taxi',
        'vehicle_plate': '1234 TAB',
        'license_number': 'L-1',
    },
    'marche': {
        'request_kind': 'emplacement',
        'market_name': 'Marché central',
        'activity': 'Légumes',
        'stall_number': '12',
    },
    'cadastre': {
        'request_kind': 'extrait',
        'parcel_reference': 'P-33',
        'district': 'Tanambao',
        'title_number': 'T-9',
    },
    'impot_foncier': {
        'request_kind': 'declaration',
        'property_address': 'Rue 2',
        'tax_year': '2024',
        'tax_reference': 'IF-1',
    },
}


def fake_verify_token(token):
    """Jetons de test : « user_xxx » est valide et vaut l'identifiant « user_xxx »."""
    if token.startswith('user_'):
        return token
    raise InvalidToken()


def make_payload(dossier_type='naissance', **overrides):
    payload = {
        'dossier_type': dossier_type,
        'guichet': '',
        'identity': dict(IDENTITY),
        # Type inconnu (tests de validation) : détails d'une demande de naissance.
        'details': dict(VALID_DETAILS.get(dossier_type, VALID_DETAILS['naissance'])
                        if isinstance(dossier_type, str) else VALID_DETAILS['naissance']),
    }
    payload.update(overrides)
    return payload


def make_dossier(user='user_a', **overrides):
    fields = {
        'clerk_user_id': user,
        'dossier_type': 'naissance',
        'identity': dict(IDENTITY),
        'details': dict(VALID_DETAILS['naissance']),
    }
    fields.update(overrides)
    return DossierRequest.objects.create(**fields)


class SchemaTests(SimpleTestCase):
    def test_every_dossier_type_has_a_schema_and_a_valid_sample(self):
        self.assertEqual(set(DossierRequest.DossierType.values), set(DETAIL_FIELDS))
        self.assertEqual(set(VALID_DETAILS), set(DETAIL_FIELDS))
        for dossier_type, specs in DETAIL_FIELDS.items():
            required = {spec.name for spec in specs if spec.required}
            self.assertTrue(required <= set(VALID_DETAILS[dossier_type]), dossier_type)


@override_settings(**CLERK_SETTINGS)
class EspaceTestCase(TestCase):
    """Base : cache vidé (limites de débit) et vérification du jeton simulée."""

    def setUp(self):
        cache.clear()
        patcher = mock.patch('espace.auth.verify_clerk_token', side_effect=fake_verify_token)
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, method, url, payload=None, user='user_a', raw=None):
        extra = {}
        if user:
            extra['HTTP_AUTHORIZATION'] = f'Bearer {user}'
        if method == 'get':
            return self.client.get(url, **extra)
        body = raw if raw is not None else json.dumps(payload if payload is not None else {})
        return getattr(self.client, method)(url, data=body, content_type='application/json', **extra)

    def create(self, payload=None, user='user_a'):
        # `is None` : un corps vide ({}) doit être envoyé tel quel, pas remplacé par une demande valide.
        payload = make_payload() if payload is None else payload
        return self.call('post', reverse('dossier_collection'), payload, user=user)


class AuthenticationTests(EspaceTestCase):
    def test_missing_token_is_401(self):
        response = self.call('get', reverse('dossier_collection'), user=None)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {'detail': 'authentication_required'})

    def test_invalid_token_is_401(self):
        response = self.call('get', reverse('dossier_collection'), user='bogus')
        self.assertEqual(response.status_code, 401)

    def test_other_scheme_is_401(self):
        response = self.client.get(reverse('dossier_collection'), HTTP_AUTHORIZATION='Basic user_a')
        self.assertEqual(response.status_code, 401)

    def test_all_dossier_routes_require_authentication(self):
        for method, url in (
            ('get', reverse('dossier_collection')),
            ('post', reverse('dossier_collection')),
            ('post', reverse('dossier_read_all')),
            ('post', reverse('dossier_mark_read', args=[1])),
        ):
            response = self.call(method, url, user=None)
            self.assertEqual(response.status_code, 401, (method, url))

    @override_settings(CLERK_ISSUER='', CLERK_PUBLISHABLE_KEY='')
    def test_not_configured_is_503(self):
        response = self.call('get', reverse('dossier_collection'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'detail': 'auth_not_configured'})

    def test_method_not_allowed(self):
        response = self.call('put', reverse('dossier_collection'), {})
        self.assertEqual(response.status_code, 405)


class IssuerDerivationTests(SimpleTestCase):
    @staticmethod
    def make_key(prefix, host):
        encoded = base64.b64encode(f'{host}$'.encode()).decode().rstrip('=')
        return f'{prefix}{encoded}'

    def test_test_and_live_keys(self):
        for prefix in ('pk_test_', 'pk_live_'):
            key = self.make_key(prefix, 'example-instance-1.clerk.accounts.dev')
            self.assertEqual(
                auth.issuer_from_publishable_key(key),
                'https://example-instance-1.clerk.accounts.dev',
            )

    def test_unreadable_keys_give_empty_issuer(self):
        for key in ('', None, 'garbage', 'pk_test_', 'pk_test_/w==', 'sk_test_abc', 'pk_test_!!!'):
            self.assertEqual(auth.issuer_from_publishable_key(key), '', key)

    @override_settings(CLERK_ISSUER='https://explicit.example.test/', CLERK_PUBLISHABLE_KEY='', CLERK_JWKS_URL='')
    def test_explicit_issuer_wins_and_jwks_default(self):
        self.assertEqual(auth.get_issuer(), 'https://explicit.example.test')
        self.assertEqual(auth.get_jwks_url(), 'https://explicit.example.test/.well-known/jwks.json')

    @override_settings(CLERK_ISSUER='', CLERK_JWKS_URL='https://keys.example.test/jwks')
    def test_explicit_jwks_url(self):
        self.assertEqual(auth.get_jwks_url(), 'https://keys.example.test/jwks')

    def test_issuer_derived_from_publishable_key(self):
        key = self.make_key('pk_test_', 'derived-1.clerk.accounts.dev')
        with override_settings(CLERK_ISSUER='', CLERK_PUBLISHABLE_KEY=key, CLERK_JWKS_URL=''):
            self.assertEqual(auth.get_issuer(), 'https://derived-1.clerk.accounts.dev')
            self.assertEqual(
                auth.get_jwks_url(), 'https://derived-1.clerk.accounts.dev/.well-known/jwks.json'
            )


@override_settings(**CLERK_SETTINGS)
class VerifyClerkTokenTests(SimpleTestCase):
    """Vérifie réellement la signature RS256, avec une clé générée pour le test."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        public_key = self.private_key.public_key()
        fake_client = types.SimpleNamespace(
            get_signing_key_from_jwt=lambda token: types.SimpleNamespace(key=public_key)
        )
        patcher = mock.patch('espace.auth._get_jwk_client', return_value=fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def token(self, key=None, **overrides):
        now = int(time.time())
        payload = {'sub': 'user_123', 'iss': ISSUER, 'exp': now + 300, 'nbf': now - 5}
        payload.update(overrides)
        return jwt.encode(payload, key or self.private_key, algorithm='RS256')

    def test_valid_token(self):
        self.assertEqual(auth.verify_clerk_token(self.token()), 'user_123')

    def test_wrong_issuer(self):
        with self.assertRaises(InvalidToken):
            auth.verify_clerk_token(self.token(iss='https://evil.example.test'))

    def test_expired_token(self):
        with self.assertRaises(InvalidToken):
            auth.verify_clerk_token(self.token(exp=int(time.time()) - 3600))

    def test_missing_subject(self):
        token = jwt.encode(
            {'iss': ISSUER, 'exp': int(time.time()) + 300}, self.private_key, algorithm='RS256'
        )
        with self.assertRaises(InvalidToken):
            auth.verify_clerk_token(token)

    def test_wrong_signature(self):
        with self.assertRaises(InvalidToken):
            auth.verify_clerk_token(self.token(key=self.other_key))

    def test_garbage_token(self):
        with self.assertRaises(InvalidToken):
            auth.verify_clerk_token('not-a-jwt')

    def test_hmac_token_is_refused(self):
        token = jwt.encode(
            {'sub': 'user_123', 'iss': ISSUER, 'exp': int(time.time()) + 300},
            'x' * 40,
            algorithm='HS256',
        )
        with self.assertRaises(InvalidToken):
            auth.verify_clerk_token(token)

    @override_settings(CLERK_AUTHORIZED_PARTIES=['http://localhost:5173'])
    def test_authorized_party(self):
        self.assertEqual(
            auth.verify_clerk_token(self.token(azp='http://localhost:5173/')), 'user_123'
        )
        with self.assertRaises(InvalidToken):
            auth.verify_clerk_token(self.token(azp='https://evil.example.test'))

    @override_settings(CLERK_ISSUER='', CLERK_PUBLISHABLE_KEY='')
    def test_not_configured(self):
        with self.assertRaises(AuthNotConfigured):
            auth.verify_clerk_token(self.token())


class DossierCreateTests(EspaceTestCase):
    def test_every_type_can_be_created(self):
        for dossier_type in DETAIL_FIELDS:
            response = self.create(make_payload(dossier_type))
            self.assertEqual(response.status_code, 201, (dossier_type, response.content))
            body = response.json()
            dossier = DossierRequest.objects.get(pk=body['id'])
            year = timezone.localtime(dossier.created_at).year
            self.assertEqual(body['reference'], f'MV-{year}-{dossier.pk:06d}')
            self.assertRegex(body['reference'], r'^MV-\d{4}-\d{6}$')
            self.assertEqual(body['status'], 'PENDING')
            self.assertTrue(body['created_at'])
            self.assertEqual(dossier.clerk_user_id, 'user_a')
            self.assertEqual(dossier.dossier_type, dossier_type)
            self.assertEqual(dossier.details, VALID_DETAILS[dossier_type])
            self.assertEqual(dossier.identity, IDENTITY)
            self.assertEqual(dossier.reference, body['reference'])

    def test_guichet_is_set_by_the_server(self):
        # Le guichet suit le type de la demande (aiguillage automatique), pas la valeur envoyée.
        from agents.guichets import guichet_for_type

        payload = make_payload(guichet='2-C')
        response = self.create(payload)
        self.assertEqual(response.status_code, 201)
        dossier = DossierRequest.objects.get()
        self.assertEqual(dossier.guichet, str(guichet_for_type(dossier.dossier_type)))

    def test_comment_accepted_for_every_type_and_unknown_or_empty_values_dropped(self):
        payload = make_payload()
        payload['details'].update({'comment': ' Merci ', 'father_name': '', 'hack': 'x'})
        payload['identity'].update({'address': '', 'unknown': 'x'})
        response = self.create(payload)
        self.assertEqual(response.status_code, 201)
        dossier = DossierRequest.objects.get()
        self.assertEqual(dossier.details['comment'], 'Merci')
        self.assertNotIn('father_name', dossier.details)
        self.assertNotIn('hack', dossier.details)
        self.assertNotIn('address', dossier.identity)
        self.assertNotIn('unknown', dossier.identity)

    def test_optional_fields_may_be_omitted(self):
        payload = make_payload('urbanisme')
        for name in ('surface', 'cadastral_reference'):
            payload['details'].pop(name)
        for name in ('national_id', 'address'):
            payload['identity'].pop(name)
        payload.pop('guichet')
        self.assertEqual(self.create(payload).status_code, 201)

    def test_email_and_phone_are_optional(self):
        payload = make_payload()
        for name in ('email', 'phone'):
            payload['identity'].pop(name)
        errors = self.create(payload).json().get('errors', {})
        self.assertNotIn('identity.email', errors)
        self.assertNotIn('identity.phone', errors)

    def test_national_id_must_have_12_digits(self):
        for value in ('101 234 567', '1012345678901', '10123456789a'):
            payload = make_payload()
            payload['identity']['national_id'] = value
            response = self.create(payload)
            self.assertEqual(response.status_code, 400, value)
            self.assertEqual(response.json()['errors']['identity.national_id'], ['invalid'])
        for value in ('101234567890', '101 234 567 890'):
            payload = make_payload()
            payload['identity']['national_id'] = value
            self.assertNotIn('identity.national_id', self.create(payload).json().get('errors', {}), value)

    def test_numbers_may_be_sent_as_json_numbers(self):
        payload = make_payload()
        payload['details']['copies'] = 2
        self.assertEqual(self.create(payload).status_code, 201)
        self.assertEqual(DossierRequest.objects.get().details['copies'], '2')

    def test_empty_body_reports_required_fields(self):
        response = self.create({})
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertEqual(errors['dossier_type'], ['required'])
        for name in ('last_name', 'first_name'):
            self.assertEqual(errors[f'identity.{name}'], ['required'])
        for name in ('email', 'phone', 'address'):
            self.assertNotIn(f'identity.{name}', errors)
        self.assertEqual(DossierRequest.objects.count(), 0)

    def test_missing_details_are_required(self):
        payload = make_payload()
        del payload['details']
        errors = self.create(payload).json()['errors']
        for name in (
            'concerned_last_name',
            'concerned_first_name',
            'birth_date',
            'birth_place',
            'mother_name',
            'copies',
        ):
            self.assertEqual(errors[f'details.{name}'], ['required'], name)
        self.assertNotIn('details.father_name', errors)

    def test_unknown_dossier_type(self):
        for value in ('xxx', 42, ['naissance']):
            errors = self.create(make_payload(dossier_type=value)).json()['errors']
            self.assertEqual(errors['dossier_type'], ['invalid'], value)

    def test_invalid_values(self):
        cases = [
            ('naissance', 'details', 'birth_date', '2020-13-45'),
            ('naissance', 'details', 'birth_date', '17/05/2001'),
            ('naissance', 'details', 'copies', '0'),
            ('naissance', 'details', 'copies', '11'),
            ('naissance', 'details', 'copies', 'deux'),
            ('deces', 'details', 'relationship', 'cousin'),
            ('urbanisme', 'details', 'request_kind', 'nope'),
            ('urbanisme', 'details', 'surface', '12 m2'),
            ('recette', 'details', 'amount', '12,5,6'),
            ('impot_foncier', 'details', 'tax_year', '1999'),
            ('impot_foncier', 'details', 'tax_year', '2101'),
            ('naissance', 'identity', 'email', 'pas-un-email'),
            ('naissance', 'identity', 'phone', 'abc'),
        ]
        for dossier_type, block, name, value in cases:
            payload = make_payload(dossier_type)
            payload[block][name] = value
            response = self.create(payload)
            self.assertEqual(response.status_code, 400, (dossier_type, name, value))
            self.assertEqual(
                response.json()['errors'][f'{block}.{name}'], ['invalid'], (dossier_type, name, value)
            )
        self.assertEqual(DossierRequest.objects.count(), 0)

    def test_too_long_values(self):
        payload = make_payload()
        payload['identity']['last_name'] = 'a' * 101
        payload['details']['birth_place'] = 'b' * 201
        payload['details']['comment'] = 'c' * 2001
        errors = self.create(payload).json()['errors']
        self.assertEqual(errors['identity.last_name'], ['too_long'])
        self.assertEqual(errors['details.birth_place'], ['too_long'])
        self.assertEqual(errors['details.comment'], ['too_long'])

    def test_invalid_guichet(self):
        for value in ('6-A', '1-F', 'A', '1A', 12):
            errors = self.create(make_payload(guichet=value)).json()['errors']
            self.assertEqual(errors['guichet'], ['invalid'], value)

    def test_invalid_json(self):
        response = self.call('post', reverse('dossier_collection'), raw='{pas du json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'errors': {'__all__': ['invalid_json']}})

    def test_json_body_must_be_an_object(self):
        response = self.call('post', reverse('dossier_collection'), raw='[1, 2]')
        self.assertEqual(response.status_code, 400)

    @override_settings(DOSSIER_RATE_LIMIT=(2, 3600))
    def test_rate_limit_is_per_user(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create().status_code, 201)
        response = self.create()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {'detail': 'throttled'})
        self.assertEqual(self.create(user='user_b').status_code, 201)


class DossierListTests(EspaceTestCase):
    LIST_KEYS = {
        'id',
        'reference',
        'dossier_type',
        'guichet',
        'status',
        'created_at',
        'updated_at',
        'response_message',
        'responded_at',
        'response_read',
        'documents',
    }

    def list(self, user='user_a'):
        response = self.call('get', reverse('dossier_collection'), user=user)
        self.assertEqual(response.status_code, 200)
        return response.json()['results']

    def test_empty_list(self):
        self.assertEqual(self.list(), [])

    def test_list_shape_and_order(self):
        old = make_dossier(dossier_type='recette', details=VALID_DETAILS['recette'])
        DossierRequest.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
        new = make_dossier(response_message='Votre dossier est prêt.')
        results = self.list()
        self.assertEqual([item['id'] for item in results], [new.id, old.id])
        for item in results:
            self.assertEqual(set(item), self.LIST_KEYS)
        self.assertEqual(results[0]['response_message'], 'Votre dossier est prêt.')
        self.assertTrue(results[0]['responded_at'])
        self.assertFalse(results[0]['response_read'])
        self.assertEqual(results[1]['response_message'], '')
        self.assertIsNone(results[1]['responded_at'])
        self.assertRegex(results[0]['reference'], r'^MV-\d{4}-\d{6}$')

    def test_users_only_see_their_own_dossiers(self):
        mine = make_dossier('user_a')
        make_dossier('user_b')
        self.assertEqual([item['id'] for item in self.list('user_a')], [mine.id])
        self.assertEqual(len(self.list('user_b')), 1)
        self.assertEqual(self.list('user_c'), [])

    def test_list_is_capped_at_200(self):
        DossierRequest.objects.bulk_create(
            [
                DossierRequest(clerk_user_id='user_a', dossier_type='naissance', identity={}, details={})
                for _ in range(205)
            ]
        )
        self.assertEqual(len(self.list()), 200)


class ReadTests(EspaceTestCase):
    def test_mark_read(self):
        dossier = make_dossier(response_message='Prêt.')
        response = self.call('post', reverse('dossier_mark_read', args=[dossier.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        dossier.refresh_from_db()
        self.assertTrue(dossier.response_read)

    def test_mark_read_of_someone_else_is_404(self):
        dossier = make_dossier('user_a', response_message='Prêt.')
        response = self.call('post', reverse('dossier_mark_read', args=[dossier.pk]), user='user_b')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'detail': 'not_found'})
        dossier.refresh_from_db()
        self.assertFalse(dossier.response_read)

    def test_mark_read_unknown_id_is_404(self):
        response = self.call('post', reverse('dossier_mark_read', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_read_requires_post(self):
        dossier = make_dossier(response_message='Prêt.')
        response = self.call('get', reverse('dossier_mark_read', args=[dossier.pk]))
        self.assertEqual(response.status_code, 405)

    def test_read_all(self):
        first = make_dossier('user_a', response_message='Un.')
        second = make_dossier('user_a', response_message='Deux.')
        without_response = make_dossier('user_a')
        other = make_dossier('user_b', response_message='Autre.')

        response = self.call('post', reverse('dossier_read_all'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'updated': 2})

        for dossier in (first, second, other, without_response):
            dossier.refresh_from_db()
        self.assertTrue(first.response_read)
        self.assertTrue(second.response_read)
        self.assertFalse(other.response_read)
        self.assertFalse(without_response.response_read)

        # Rien de plus à marquer au deuxième appel.
        response = self.call('post', reverse('dossier_read_all'))
        self.assertEqual(response.json(), {'updated': 0})


class ResponseTrackingTests(TestCase):
    """Un changement de réponse (admin) repasse le dossier en « non lu »."""

    def test_new_response_sets_date_and_unread(self):
        dossier = make_dossier()
        self.assertIsNone(dossier.responded_at)
        self.assertFalse(dossier.response_read)

        dossier.response_message = 'Votre acte est prêt.'
        dossier.save()
        dossier.refresh_from_db()
        self.assertIsNotNone(dossier.responded_at)
        self.assertFalse(dossier.response_read)

    def test_unchanged_response_keeps_read_flag(self):
        dossier = make_dossier(response_message='Prêt.')
        DossierRequest.objects.filter(pk=dossier.pk).update(response_read=True)
        dossier.refresh_from_db()
        dossier.save()
        dossier.refresh_from_db()
        self.assertTrue(dossier.response_read)

    def test_modified_response_becomes_unread_again(self):
        dossier = make_dossier(response_message='Prêt.')
        DossierRequest.objects.filter(pk=dossier.pk).update(response_read=True)
        dossier.refresh_from_db()
        dossier.response_message = 'Prêt, à retirer au guichet 2.'
        dossier.save()
        dossier.refresh_from_db()
        self.assertFalse(dossier.response_read)

    def test_cleared_response_removes_date(self):
        dossier = make_dossier(response_message='Prêt.')
        dossier.response_message = ''
        dossier.save()
        dossier.refresh_from_db()
        self.assertIsNone(dossier.responded_at)

    def test_update_fields_still_stores_tracking_fields(self):
        dossier = make_dossier()
        dossier.response_message = 'Prêt.'
        dossier.save(update_fields=['response_message'])
        dossier.refresh_from_db()
        self.assertEqual(dossier.response_message, 'Prêt.')
        self.assertIsNotNone(dossier.responded_at)
        self.assertFalse(dossier.response_read)

    def test_reference_is_unique_and_set_on_creation(self):
        first, second = make_dossier(), make_dossier()
        self.assertNotEqual(first.reference, second.reference)
        self.assertTrue(re.match(r'^MV-\d{4}-\d{6}$', first.reference))


@override_settings(CLERK_ISSUER='', CLERK_PUBLISHABLE_KEY='')  # le contact est public
class ContactTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, payload=None, raw=None):
        body = raw if raw is not None else json.dumps(payload)
        return self.client.post(reverse('contact_create'), data=body, content_type='application/json')

    def valid(self, **overrides):
        payload = {
            'first_name': 'Aina',
            'last_name': 'RAKOTO',
            'phone': '+261 34 00 000 00',
            'email': 'aina@example.com',
            'message': 'Bonjour, je souhaite un renseignement.',
        }
        payload.update(overrides)
        return payload

    def test_contact_is_created_without_authentication(self):
        response = self.post(self.valid())
        self.assertEqual(response.status_code, 201)
        message = ContactMessage.objects.get()
        self.assertEqual(response.json(), {'id': message.id})
        self.assertEqual(message.first_name, 'Aina')
        self.assertEqual(message.email, 'aina@example.com')
        self.assertFalse(message.handled)

    def test_last_name_and_message_are_optional(self):
        payload = self.valid()
        del payload['last_name']
        del payload['message']
        self.assertEqual(self.post(payload).status_code, 201)
        message = ContactMessage.objects.get()
        self.assertEqual(message.last_name, '')
        self.assertEqual(message.message, '')

    def test_required_fields(self):
        response = self.post({})
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertEqual(errors['first_name'], ['required'])
        self.assertEqual(errors['phone'], ['required'])
        self.assertEqual(errors['email'], ['required'])
        self.assertNotIn('last_name', errors)
        self.assertNotIn('message', errors)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_invalid_values(self):
        errors = self.post(self.valid(email='nope', phone='abc')).json()['errors']
        self.assertEqual(errors['email'], ['invalid'])
        self.assertEqual(errors['phone'], ['invalid'])
        errors = self.post(self.valid(message='m' * 2001)).json()['errors']
        self.assertEqual(errors['message'], ['too_long'])

    def test_invalid_json(self):
        self.assertEqual(self.post(raw='{oups').status_code, 400)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse('contact_create')).status_code, 405)

    @override_settings(CONTACT_RATE_LIMIT=(2, 3600))
    def test_rate_limit_per_ip(self):
        self.assertEqual(self.post(self.valid()).status_code, 201)
        self.assertEqual(self.post(self.valid()).status_code, 201)
        response = self.post(self.valid())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {'detail': 'throttled'})


class AdminSmokeTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'mot-de-passe-test-1')
        self.client.force_login(self.admin)
        make_dossier()
        ContactMessage.objects.create(first_name='Aina', phone='0340000000', email='a@example.com')

    def test_changelists_and_search(self):
        for name in ('espace_dossierrequest_changelist', 'espace_contactmessage_changelist'):
            self.assertEqual(self.client.get(reverse(f'admin:{name}')).status_code, 200, name)
        response = self.client.get(reverse('admin:espace_dossierrequest_changelist'), {'q': 'RAKOTO'})
        self.assertEqual(response.status_code, 200)

    def test_change_page(self):
        dossier = DossierRequest.objects.get()
        response = self.client.get(reverse('admin:espace_dossierrequest_change', args=[dossier.pk]))
        self.assertEqual(response.status_code, 200)


class CitizenMailTests(EspaceTestCase):
    """Mail de l'usager : il écrit à un guichet, l'agent répond depuis sa boîte Mail."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model

        from agents.models import AgentProfile

        self.agent = get_user_model().objects.create_user('naissance', 'agent1@example.com', 'motdepasse-123-abc')
        AgentProfile.objects.create(user=self.agent, guichet=1)
        self.other = get_user_model().objects.create_user('mariage', 'agent2@example.com', 'motdepasse-123-abc')
        AgentProfile.objects.create(user=self.other, guichet=2)

    def write(self, user='user_a', **overrides):
        payload = {'service': '1', 'subject': 'Ma copie', 'body': 'Bonjour', 'sender_name': 'Jean RABE',
                   'sender_email': 'jean@example.com', **overrides}
        return self.call('post', reverse('mail_collection'), payload, user=user)

    def test_message_reaches_only_the_chosen_guichet(self):
        from messagerie.models import Mail

        self.assertEqual(self.write().status_code, 201)
        received = Mail.objects.get(owner=self.agent)
        self.assertEqual((received.folder, received.citizen_id, received.is_read), ('INBOX', 'user_a', False))
        self.assertFalse(Mail.objects.filter(owner=self.other).exists())
        listing = self.call('get', reverse('mail_collection')).json()
        self.assertEqual([m['folder'] for m in listing['results']], ['sent'])
        self.assertEqual(self.call('get', reverse('mail_collection'), user='user_b').json()['results'], [])

    def test_validation(self):
        errors = self.write(service='9', body='').json()['errors']
        self.assertEqual(errors['service'], ['invalid'])
        self.assertEqual(errors['body'], ['required'])
        self.assertEqual(self.write(sender_email='pas-un-mail').json()['errors']['sender_email'], ['invalid'])

    def test_agent_reply_arrives_in_citizen_space(self):
        from messagerie.models import Mail

        self.write()
        received = Mail.objects.get(owner=self.agent)
        self.client.force_login(self.agent)
        url = reverse('agents:mail', args=[1])
        page = self.client.get(f'{url}?m={received.pk}&compose=new&reply={received.pk}')
        self.assertContains(page, 'name="citizen" value="user_a"')
        response = self.client.post(url, {
            'action': 'send', 'to': 'jean@example.com', 'subject': 'Re: Ma copie', 'body': 'Elle est prête.',
            'citizen': 'user_a',
        }, follow=True)
        self.assertContains(response, 'Message envoyé.')  # lu dans l'espace : pas d'avertissement SMTP

        results = self.call('get', reverse('mail_collection')).json()['results']
        reply = next(m for m in results if m['folder'] == 'inbox')
        self.assertEqual(reply['body'], 'Elle est prête.')
        self.assertEqual(reply['service'], '1')
        self.assertFalse(reply['is_read'])
        self.assertEqual(self.call('post', reverse('mail_mark_read', args=[reply['id']]), user='user_b').status_code, 404)
        self.call('post', reverse('mail_mark_read', args=[reply['id']]))
        self.assertTrue(Mail.objects.get(pk=reply['id']).is_read)

    def test_agent_cannot_push_to_a_citizen_who_never_wrote(self):
        from messagerie.models import Mail

        self.client.force_login(self.agent)
        self.client.post(reverse('agents:mail', args=[1]), {
            'action': 'send', 'to': 'x@example.com', 'subject': 'S', 'body': 'B', 'citizen': 'user_z',
        })
        self.assertFalse(Mail.objects.filter(owner=None, citizen_id='user_z').exists())


class CitizenAssistantTests(EspaceTestCase):
    def ask(self, message, user='user_a'):
        return self.call('post', reverse('espace_assistant'), {'message': message}, user=user).json()

    def test_status_of_own_requests_only(self):
        dossier = make_dossier()
        other = make_dossier(user='user_b')
        reply = self.ask('Où en sont mes demandes ?')
        self.assertIn(dossier.reference, reply['items'][0]['label'])
        self.assertIn(other.reference, self.ask(f'statut {other.reference}', user='user_b')['text'])
        self.assertIn('Je ne trouve pas', self.ask(f'statut {other.reference}')['text'])

    def test_points_to_the_right_procedure(self):
        reply = self.ask('Je veux un permis de construire')
        self.assertEqual(reply['items'][0]['url'], '/espace/demande/urbanisme')

    def test_requires_a_message(self):
        response = self.call('post', reverse('espace_assistant'), {'message': ' '})
        self.assertEqual(response.status_code, 400)


class QuartierStepTests(EspaceTestCase):
    """Étape « Quartier » : fokontany et résidence principale, obligatoires pour les actes."""

    def test_required_for_civil_acts_only(self):
        for dossier_type in ('naissance', 'mariage', 'deces', 'legislation'):
            details = {k: v for k, v in VALID_DETAILS[dossier_type].items() if k not in QUARTIER}
            errors = self.create(make_payload(dossier_type, details=details)).json()['errors']
            self.assertEqual(errors['details.fokontany'], ['required'], dossier_type)
            self.assertEqual(errors['details.main_residence'], ['required'], dossier_type)
        self.assertEqual(self.create(make_payload('recette')).status_code, 201)

    def test_unknown_fokontany_is_refused(self):
        details = {**VALID_DETAILS['naissance'], 'fokontany': 'Paris'}
        errors = self.create(make_payload('naissance', details=details)).json()['errors']
        self.assertEqual(errors['details.fokontany'], ['invalid'])

    def test_saved_with_the_request(self):
        self.assertEqual(self.create(make_payload('naissance')).status_code, 201)
        self.assertEqual(DossierRequest.objects.get().details['fokontany'], 'Mahabibo')
