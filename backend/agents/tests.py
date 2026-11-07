from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from documents.models import AgentAccessRequest
from espace.models import DossierRequest
from fichiers.models import Folder

from .models import AgentProfile

PASSWORD = 'Un-mot-de-passe-solide-42'


def make_agent(username, guichet):
    user = get_user_model().objects.create_user(username, password=PASSWORD, first_name='Agent')
    AgentProfile.objects.create(user=user, guichet=guichet)
    return user


def make_request(dossier_type, **extra):
    return DossierRequest.objects.create(
        clerk_user_id='user_123',
        dossier_type=dossier_type,
        identity={'last_name': 'RABE', 'first_name': 'Jean', 'email': 'jean@example.com'},
        details={'copies': '1'},
        **extra,
    )


class ConnexionTests(TestCase):
    def login(self, username, password=PASSWORD, **params):
        url = reverse('connexion')
        if params:
            url += '?' + '&'.join(f'{k}={v}' for k, v in params.items())
        return self.client.post(url, {'username': username, 'password': password})

    def test_agent_goes_to_own_guichet(self):
        make_agent('naissance', 1)
        response = self.login('naissance')
        self.assertRedirects(response, reverse('agents:dashboard', args=[1]))

    def test_admin_goes_to_admin(self):
        get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        response = self.login('chef')
        self.assertRedirects(response, reverse('admin:index'))

    def test_account_without_role_is_refused(self):
        get_user_model().objects.create_user('inconnu', password=PASSWORD)
        response = self.login('inconnu')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "n&#x27;a pas encore de rôle")
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_agent_ignores_next_outside_agent_space(self):
        make_agent('deces', 3)
        response = self.login('deces', next='/admin/')
        self.assertRedirects(response, reverse('agents:dashboard', args=[3]))

    def test_admin_login_page_redirects_to_connexion(self):
        response = self.client.get(reverse('admin:login'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('connexion')))

    def test_agent_cannot_open_admin(self):
        make_agent('mariage', 2)
        self.client.login(username='mariage', password=PASSWORD)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'], reverse('admin:index'))


class GuichetAccessTests(TestCase):
    def setUp(self):
        self.agent = make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)

    def test_own_dashboard(self):
        self.assertEqual(self.client.get(reverse('agents:dashboard', args=[1])).status_code, 200)

    def test_other_guichet_is_forbidden(self):
        for number in (2, 3, 4, 5):
            response = self.client.get(reverse('agents:dashboard', args=[number]))
            self.assertEqual(response.status_code, 403)
            response = self.client.get(reverse('agents:requests', args=[number]))
            self.assertEqual(response.status_code, 403)

    def test_list_only_shows_own_dossier_types(self):
        mine = make_request(DossierRequest.DossierType.NAISSANCE)
        other = make_request(DossierRequest.DossierType.MARIAGE)
        response = self.client.get(reverse('agents:requests', args=[1]))
        self.assertContains(response, mine.reference)
        self.assertNotContains(response, other.reference)

    def test_detail_of_other_guichet_is_not_found(self):
        other = make_request(DossierRequest.DossierType.TRANSPORT)
        response = self.client.get(reverse('agents:request_detail', args=[1, other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_agent_home_redirects_to_own_guichet(self):
        self.assertRedirects(self.client.get(reverse('agents:home')), reverse('agents:dashboard', args=[1]))

    def test_anonymous_is_sent_to_connexion(self):
        self.client.logout()
        response = self.client.get(reverse('agents:dashboard', args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('connexion')))

    def test_guichet_5_groups_services(self):
        make_agent('services', 5)
        self.client.login(username='services', password=PASSWORD)
        for dossier_type in ('recette', 'transport', 'marche', 'urbanisme', 'cadastre', 'impot_foncier'):
            dossier = make_request(dossier_type)
            response = self.client.get(reverse('agents:request_detail', args=[5, dossier.pk]))
            self.assertEqual(response.status_code, 200, dossier_type)


class DecisionTests(TestCase):
    def setUp(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        self.dossier = make_request(DossierRequest.DossierType.NAISSANCE)
        self.url = reverse('agents:request_detail', args=[1, self.dossier.pk])

    def test_reply_reaches_the_user(self):
        response = self.client.post(self.url, {'status': 'APPROVED', 'response_message': 'Votre acte est prêt.'})
        self.assertRedirects(response, self.url)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.status, 'APPROVED')
        self.assertEqual(self.dossier.response_message, 'Votre acte est prêt.')
        self.assertIsNotNone(self.dossier.responded_at)
        self.assertFalse(self.dossier.response_read)

    def test_final_status_requires_a_reply(self):
        response = self.client.post(self.url, {'status': 'REJECTED', 'response_message': '  '})
        self.assertEqual(response.status_code, 200)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.status, 'PENDING')

    def test_in_progress_without_reply_is_allowed(self):
        self.client.post(self.url, {'status': 'IN_PROGRESS', 'response_message': ''})
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.status, 'IN_PROGRESS')


class ApprovalTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        self.client.force_login(self.admin)

    def approve(self, access_request):
        return self.client.post(
            reverse('admin:documents_agentaccessrequest_changelist'),
            {'action': 'approve_requests', '_selected_action': [access_request.pk]},
            follow=True,
        )

    def test_approval_creates_agent_account(self):
        access_request = AgentAccessRequest.objects.create(
            first_name='Hery', last_name='Rakoto', phone_number='0340000000',
            email='hery@example.com', request_type='AGENT_ACCESS', guichet=2,
        )
        response = self.approve(access_request)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AgentAccessRequest.Status.APPROVED)
        user = access_request.agent_user
        self.assertEqual(user.username, 'hery.rakoto')
        self.assertFalse(user.is_staff)
        self.assertEqual(user.agent_profile.guichet, 2)
        text = ' '.join(str(m) for m in get_messages(response.wsgi_request))
        self.assertIn('hery.rakoto', text)

    def test_approval_needs_a_guichet(self):
        access_request = AgentAccessRequest.objects.create(
            first_name='Sans', last_name='Guichet', phone_number='0340000000',
            email='sg@example.com', request_type='AGENT_ACCESS',
        )
        self.approve(access_request)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AgentAccessRequest.Status.PENDING)
        self.assertIsNone(access_request.agent_user)


class InscriptionFlowTests(TestCase):
    """Parcours complet : demande d'accès → validation par l'admin → connexion sur son guichet."""

    def signup(self, **overrides):
        data = {
            'last_name': 'Rasoa', 'first_name': 'Lala', 'email': 'Lala@Example.com',
            'password1': PASSWORD, 'password2': PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse('agents:inscription'), data)

    def login(self, username, password=PASSWORD):
        return self.client.post(reverse('connexion'), {'username': username, 'password': password})

    def test_full_flow(self):
        response = self.signup()
        self.assertContains(response, 'Demande envoyée')
        access_request = AgentAccessRequest.objects.get()
        self.assertEqual(access_request.email, 'lala@example.com')
        self.assertIsNone(access_request.guichet)  # l'agent ne choisit pas son rôle
        self.assertNotIn(PASSWORD, access_request.password_hash)
        self.assertTrue(access_request.password_hash)

        # Avant validation : connexion refusée, avec explication.
        response = self.login('lala@example.com')
        self.assertContains(response, 'en attente de validation')

        admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        self.client.force_login(admin_user)
        access_request.guichet = 1  # attribué par l'administrateur
        access_request.save(update_fields=['guichet'])
        self.client.post(
            reverse('admin:documents_agentaccessrequest_changelist'),
            {'action': 'approve_requests', '_selected_action': [access_request.pk]},
        )
        self.client.logout()

        access_request.refresh_from_db()
        self.assertEqual(access_request.password_hash, '')
        self.assertEqual(access_request.agent_user.username, 'lala@example.com')

        # Après validation : ses propres identifiants, et directement son guichet.
        response = self.login('lala@example.com')
        self.assertRedirects(response, reverse('agents:dashboard', args=[1]))
        self.assertEqual(self.client.get(reverse('agents:dashboard', args=[2])).status_code, 403)

    def test_passwords_must_match(self):
        response = self.signup(password2='autre-chose-123!')
        self.assertContains(response, 'ne correspondent pas')
        self.assertFalse(AgentAccessRequest.objects.exists())

    def test_weak_password_is_refused(self):
        response = self.signup(password1='123', password2='123')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AgentAccessRequest.objects.exists())

    def test_agent_cannot_choose_a_guichet(self):
        self.signup(guichet='3')
        self.assertIsNone(AgentAccessRequest.objects.get().guichet)
        self.assertNotContains(self.client.get(reverse('agents:inscription')), 'Guichet souhaité')

    def test_duplicate_pending_request_is_refused(self):
        self.signup()
        response = self.signup()
        self.assertContains(response, 'attend déjà la validation')
        self.assertEqual(AgentAccessRequest.objects.count(), 1)

    def test_rejected_request_explains_on_login(self):
        self.signup()
        AgentAccessRequest.objects.update(status=AgentAccessRequest.Status.REJECTED)
        self.assertContains(self.login('lala@example.com'), 'refusée')

    def test_login_page_links_to_inscription(self):
        self.assertContains(self.client.get(reverse('connexion')), reverse('agents:inscription'))


ACT_DATA = {
    'region': 'Boeny', 'district': 'Mahajanga I', 'commune': 'Commune Urbaine de Mahajanga',
    'act_datetime': '2026-05-16T10:15',
    'child_last_name': 'Dubois', 'child_first_names': 'Lucas, Alexandre', 'child_sex': 'M',
    'birth_datetime': '2026-05-15T14:30', 'birth_place': 'Mahajanga',
    'father_full_name': 'Thomas DUBOIS', 'father_birth_date': '1992-03-12', 'father_birth_place': 'Antananarivo',
    'father_profession': 'ingénieur', 'father_address': '14 Rue de la Paix, Mahajanga',
    'mother_full_name': 'Sophie MARTIN', 'mother_birth_date': '1995-08-24', 'mother_birth_place': 'Toamasina',
    'mother_profession': 'juriste', 'mother_address': '14 Rue de la Paix, Mahajanga',
    'declarant_name': 'Thomas DUBOIS', 'declarant_relationship': "père de l'enfant",
    'registrar_name': 'Jean RAKOTO', 'registrar_title': "Officier de l'état civil",
    'marginal_notes': 'Sans objet.',
}


class BirthCertificateTests(TestCase):
    def setUp(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        self.create_url = reverse('agents:document_create', args=[1])

    def create(self, **overrides):
        return self.client.post(self.create_url, {**ACT_DATA, **overrides})

    def test_create_seals_and_numbers_the_act(self):
        from .models import BirthCertificate

        response = self.create()
        act = BirthCertificate.objects.get()
        self.assertRedirects(response, reverse('agents:document_detail', args=[1, act.pk]))
        self.assertEqual(act.act_number, '2026-NAI-00001')
        self.assertEqual(len(act.content_hash), 64)
        self.assertTrue(act.verify()['is_authentic'])
        self.create(child_first_names='Marie', child_sex='F')
        self.assertEqual(BirthCertificate.objects.order_by('act_number').last().act_number, '2026-NAI-00002')

    def test_pdf_download(self):
        from .models import BirthCertificate

        self.create()
        act = BirthCertificate.objects.get()
        response = self.client.get(reverse('agents:document_pdf', args=[1, act.pk]))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_public_verification(self):
        from .models import BirthCertificate

        self.create()
        act = BirthCertificate.objects.get()
        url = reverse('verify_document', args=[act.pk])
        data = self.client.get(url).json()
        self.assertTrue(data['is_authentic'])
        self.assertEqual(data['document']['signature_fingerprint'], act.content_hash)

        # Une altération en base est détectée.
        BirthCertificate.objects.filter(pk=act.pk).update(child_last_name='Faux')
        data = self.client.get(url).json()
        self.assertFalse(data['is_authentic'])
        self.assertEqual(data['status'], 'INVALID')
        self.assertIsNone(data['document'])

    def test_invalid_dates_are_refused(self):
        from .models import BirthCertificate

        response = self.create(act_datetime='2026-05-14T10:00')  # avant la naissance
        self.assertEqual(response.status_code, 200)
        response = self.create(mother_birth_date='2027-01-01')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BirthCertificate.objects.exists())

    def test_father_is_optional(self):
        from .models import BirthCertificate

        empty_father = {f'father_{f}': '' for f in ('full_name', 'birth_date', 'birth_place', 'profession', 'address')}
        self.create(**empty_father)
        self.assertEqual(BirthCertificate.objects.count(), 1)

    def test_prefill_from_request(self):
        dossier = DossierRequest.objects.create(
            clerk_user_id='u1', dossier_type='naissance',
            identity={'last_name': 'RABE', 'first_name': 'Jean', 'email': 'jean@example.com'},
            details={'concerned_last_name': 'Rabe', 'concerned_first_name': 'Hery', 'birth_date': '2026-01-02',
                     'birth_place': 'Mahajanga', 'mother_name': 'Lala'},
        )
        response = self.client.get(f'{self.create_url}?demande={dossier.pk}')
        self.assertContains(response, 'value="Hery"')
        self.assertContains(response, 'value="2026-01-02T00:00"')

        self.create(demande=dossier.pk)
        from .models import BirthCertificate

        self.assertEqual(BirthCertificate.objects.filter(request=dossier).count(), 1)

    def test_other_guichet_cannot_see_birth_certificates(self):
        make_agent('mariage', 2)
        self.client.login(username='mariage', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('agents:documents', args=[2])).status_code, 200)  # ses actes de mariage
        self.assertEqual(self.client.get(reverse('agents:documents', args=[1])).status_code, 403)


class MailAndMessagesTests(TestCase):
    def setUp(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)

    def test_mail_suggests_only_own_guichet_users(self):
        make_request('naissance')
        DossierRequest.objects.create(
            clerk_user_id='u2', dossier_type='mariage',
            identity={'last_name': 'AUTRE', 'first_name': 'X', 'email': 'autre@example.com'}, details={},
        )
        response = self.client.get(reverse('agents:mail', args=[1]))
        self.assertContains(response, '<option value="jean@example.com">')
        self.assertNotContains(response, 'autre@example.com')

    def test_messages_lists_replies(self):
        dossier = make_request('naissance')
        dossier.status = 'APPROVED'
        dossier.response_message = 'Votre acte est prêt.'
        dossier.save()
        response = self.client.get(reverse('agents:messages', args=[1]))
        self.assertContains(response, 'Votre acte est prêt.')
        self.assertContains(response, 'Non lu')


class DeleteBirthCertificateTests(TestCase):
    """L'agent demande la suppression ; seul l'administrateur l'accepte ou la refuse."""

    def setUp(self):
        from .models import BirthCertificate

        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        self.client.post(reverse('agents:document_create', args=[1]), ACT_DATA)
        self.act = BirthCertificate.objects.get()
        self.delete_url = reverse('agents:document_delete', args=[1, self.act.pk])

    def admin_action(self, action):
        admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        self.client.force_login(admin_user)
        return self.client.post(
            reverse('admin:agents_birthcertificate_changelist'),
            {'action': action, '_selected_action': [self.act.pk]},
        )

    def test_agent_only_requests_deletion(self):
        response = self.client.post(self.delete_url, {'reason': 'Erreur sur le nom'})
        self.assertRedirects(response, reverse('agents:document_detail', args=[1, self.act.pk]))
        self.act.refresh_from_db()
        self.assertIsNone(self.act.deleted_at)  # toujours là
        self.assertTrue(self.act.deletion_pending)
        self.assertEqual(self.act.deletion_reason, 'Erreur sur le nom')
        self.assertContains(self.client.get(reverse('agents:folder_documents', args=[1])), 'Suppression demandée')
        self.assertTrue(self.client.get(reverse('verify_document', args=[self.act.pk])).json()['is_authentic'])

    def test_documents_are_stored_in_folders(self):
        detail_url = reverse('agents:document_detail', args=[1, self.act.pk])
        self.assertNotContains(self.client.get(reverse('agents:documents', args=[1])), detail_url)
        folders_url = reverse('agents:folders', args=[1])
        self.assertContains(self.client.get(folders_url), reverse('agents:folder_documents', args=[1]))
        self.assertContains(self.client.get(reverse('agents:folder_documents', args=[1])), self.act.act_number)
        self.assertContains(self.client.get(folders_url, {'q': self.act.act_number}), self.act.act_number)

    def test_header_search_finds_documents_requests_and_own_files(self):
        url = reverse('agents:search', args=[1])
        self.assertContains(self.client.get(url), 'name="q"')

        response = self.client.get(url, {'q': self.act.act_number})
        self.assertContains(response, reverse('agents:document_detail', args=[1, self.act.pk]))

        dossier = make_request('naissance')
        other_guichet = make_request('transport')
        response = self.client.get(url, {'q': dossier.reference})
        self.assertContains(response, reverse('agents:request_detail', args=[1, dossier.pk]))
        response = self.client.get(url, {'q': other_guichet.reference})
        self.assertFalse(response.context['has_results'])

        agent = get_user_model().objects.get(username='naissance')
        other = make_agent('autre', 1)
        Folder.objects.create(owner=agent, name='Budget mine')
        Folder.objects.create(owner=other, name='Budget autre')
        response = self.client.get(url, {'q': 'Budget'})
        self.assertEqual([folder.name for folder in response.context['found_folders']], ['Budget mine'])

        self.assertContains(self.client.get(url, {'q': 'Paramètres'}), reverse('agents:settings'))

    def test_reason_is_required(self):
        response = self.client.post(self.delete_url, {'reason': '  '})
        self.assertEqual(response.status_code, 200)
        self.act.refresh_from_db()
        self.assertFalse(self.act.deletion_pending)

    def test_admin_approves_deletion(self):
        self.client.post(self.delete_url, {'reason': 'Doublon'}, follow=True)  # affiche (et consomme) le message
        self.admin_action('approve_deletion')
        self.act.refresh_from_db()
        self.assertIsNotNone(self.act.deleted_at)
        self.client.login(username='naissance', password=PASSWORD)
        self.assertNotContains(self.client.get(reverse('agents:folder_documents', args=[1])), self.act.act_number)
        self.assertEqual(self.client.get(reverse('verify_document', args=[self.act.pk])).json()['status'], 'REVOKED')

    def test_admin_rejects_deletion(self):
        self.client.post(self.delete_url, {'reason': 'Doublon'})
        self.admin_action('reject_deletion')
        self.act.refresh_from_db()
        self.assertIsNone(self.act.deleted_at)
        self.assertFalse(self.act.deletion_pending)

    def test_approval_needs_an_agent_request(self):
        self.admin_action('approve_deletion')  # aucune demande de l'agent : rien n'est supprimé
        self.act.refresh_from_db()
        self.assertIsNone(self.act.deleted_at)

    def test_agent_can_cancel_request(self):
        self.client.post(self.delete_url, {'reason': 'Doublon'})
        self.client.post(reverse('agents:document_cancel_deletion', args=[1, self.act.pk]))
        self.act.refresh_from_db()
        self.assertFalse(self.act.deletion_pending)

    def test_number_is_never_reused(self):
        from .models import BirthCertificate

        self.client.post(self.delete_url, {'reason': 'Doublon'})
        self.admin_action('approve_deletion')
        self.client.login(username='naissance', password=PASSWORD)
        self.client.post(reverse('agents:document_create', args=[1]), ACT_DATA)
        latest = BirthCertificate.objects.filter(deleted_at=None).get()
        self.assertEqual(latest.act_number, '2026-NAI-00002')

    def test_other_guichet_cannot_request_deletion(self):
        make_agent('mariage', 2)
        self.client.login(username='mariage', password=PASSWORD)
        self.assertEqual(self.client.post(self.delete_url, {'reason': 'x'}).status_code, 403)
        self.act.refresh_from_db()
        self.assertFalse(self.act.deletion_pending)


class RoutingAndNotificationTests(TestCase):
    """Chaque demande d'usager arrive au bon guichet et l'agent en est averti."""

    def test_each_type_is_routed_to_its_guichet(self):
        expected = {
            'naissance': '1', 'mariage': '2', 'deces': '3', 'legislation': '4',
            'recette': '5', 'transport': '5', 'marche': '5', 'cadastre': '5',
            'urbanisme': '5', 'impot_foncier': '5', 'actes_divers': '5',
        }
        for dossier_type, guichet in expected.items():
            self.assertEqual(make_request(dossier_type).guichet, guichet, dossier_type)

    def test_client_cannot_choose_the_guichet(self):
        self.assertEqual(make_request('naissance', guichet='5-A').guichet, '1')

    def test_agent_is_notified_of_new_requests(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        count_url = reverse('agents:notifications_count', args=[1])
        self.assertEqual(self.client.get(count_url).json()['new_count'], 0)

        dossier = make_request('naissance')
        make_request('transport')  # autre guichet : pas de notification ici
        data = self.client.get(count_url).json()
        self.assertEqual(data['new_count'], 1)
        self.assertEqual(data['latest']['reference'], dossier.reference)

        # La page Notifications marque les demandes comme vues.
        self.assertContains(self.client.get(reverse('agents:notifications', args=[1])), dossier.reference)
        self.assertEqual(self.client.get(count_url).json()['new_count'], 0)

    def test_notifications_and_statuses_are_cards_of_the_requests_page(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        make_request('naissance')
        response = self.client.get(reverse('agents:requests', args=[1]))
        labels = [str(item['label']) for section in response.context['mairy_nav'] for item in section['items']]
        for label in ('Notifications', 'En attente', 'En cours'):
            self.assertNotIn(label, labels)
        stats = {str(stat['label']): stat['count'] for stat in response.context['request_stats']}
        self.assertEqual(stats, {'Notifications': 1, 'En attente': 1, 'En cours': 0})

        # La page Notifications reste rattachée à « Toutes les demandes » dans le menu.
        response = self.client.get(reverse('agents:notifications', args=[1]))
        active = [str(item['label']) for section in response.context['mairy_nav'] for item in section['items'] if item['active']]
        self.assertEqual(active, ['Toutes les demandes'])
        self.assertTemplateUsed(response, 'agents/_request_stats.html')

    def test_settings_replace_password_in_sidebar(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        response = self.client.get(reverse('agents:settings'))
        labels = [str(item['label']) for section in response.context['mairy_nav'] for item in section['items']]
        self.assertIn('Paramètres', labels)
        self.assertNotIn('Mot de passe', labels)
        self.assertRedirects(self.client.get('/agent/mot-de-passe/'), reverse('agents:settings'))

    def test_settings_update_name_but_not_email(self):
        agent = make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        response = self.client.post(reverse('agents:settings'), {
            'section': 'profile', 'first_name': 'Rado', 'last_name': 'Be', 'email': 'autre@example.com',
        })
        self.assertRedirects(response, reverse('agents:settings'))
        user = get_user_model().objects.get(username='naissance')
        self.assertEqual((user.first_name, user.last_name, user.email), ('Rado', 'Be', agent.email))

    def test_settings_change_password_keeps_session(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        new_password = 'Encore-un-mot-de-passe-77'
        response = self.client.post(reverse('agents:settings'), {
            'section': 'password', 'old_password': 'mauvais',
            'new_password1': new_password, 'new_password2': new_password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['password_form'].errors)
        response = self.client.post(reverse('agents:settings'), {
            'section': 'password', 'old_password': PASSWORD,
            'new_password1': new_password, 'new_password2': new_password,
        })
        self.assertRedirects(response, reverse('agents:settings'))
        self.assertTrue(get_user_model().objects.get(username='naissance').check_password(new_password))

    def test_guichet_5_agent_is_notified_of_services(self):
        make_agent('services', 5)
        self.client.login(username='services', password=PASSWORD)
        make_request('transport')
        make_request('cadastre')
        make_request('naissance')
        self.assertEqual(self.client.get(reverse('agents:notifications_count', args=[5])).json()['new_count'], 2)


class SendToRequesterTests(TestCase):
    """L'agent envoie l'acte à l'usager ; l'usager (et lui seul) le télécharge depuis son espace."""

    def setUp(self):
        from unittest import mock

        from django.core.cache import cache
        from espace.tests import fake_verify_token

        from .models import BirthCertificate

        cache.clear()
        patcher = mock.patch('espace.auth.verify_clerk_token', side_effect=fake_verify_token)
        patcher.start()
        self.addCleanup(patcher.stop)

        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        self.dossier = DossierRequest.objects.create(
            clerk_user_id='user_a', dossier_type='naissance',
            identity={'last_name': 'RABE', 'first_name': 'Jean', 'email': 'jean@example.com'}, details={},
        )
        self.client.post(reverse('agents:document_create', args=[1]), {**ACT_DATA, 'demande': self.dossier.pk})
        self.act = BirthCertificate.objects.get()
        self.send_url = reverse('agents:document_send', args=[1, self.act.pk])

    def api(self, url, user='user_a'):
        from django.test import override_settings
        from espace.tests import CLERK_SETTINGS

        with override_settings(**CLERK_SETTINGS):
            return self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {user}')

    def download_url(self):
        return reverse('dossier_document', args=[self.dossier.pk, self.act.pk])

    def test_send_notifies_the_user(self):
        response = self.client.post(self.send_url, {'message': 'Votre acte est prêt.'})
        self.assertRedirects(response, reverse('agents:document_detail', args=[1, self.act.pk]))
        self.act.refresh_from_db()
        self.dossier.refresh_from_db()
        self.assertIsNotNone(self.act.sent_at)
        self.assertEqual(self.dossier.status, DossierRequest.Status.COMPLETED)
        self.assertEqual(self.dossier.response_message, 'Votre acte est prêt.')
        self.assertFalse(self.dossier.response_read)

    def test_user_downloads_the_pdf(self):
        self.assertEqual(self.api(self.download_url()).status_code, 404)  # pas encore envoyé
        self.client.post(self.send_url, {'message': ''})
        listed = self.api(reverse('dossier_collection')).json()['results'][0]['documents']
        self.assertEqual([d['id'] for d in listed], [str(self.act.pk)])

        response = self.api(self.download_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_other_user_cannot_download(self):
        self.client.post(self.send_url, {'message': ''})
        self.assertEqual(self.api(self.download_url(), user='user_b').status_code, 404)
        self.assertEqual(self.client.get(self.download_url()).status_code, 401)  # sans jeton

    def test_resend_notifies_again(self):
        self.client.post(self.send_url, {'message': 'Prêt.'})
        DossierRequest.objects.filter(pk=self.dossier.pk).update(response_read=True)
        self.client.post(self.send_url, {'message': 'Prêt.'})
        self.dossier.refresh_from_db()
        self.assertFalse(self.dossier.response_read)

    def test_act_without_request_needs_a_target(self):
        from .models import BirthCertificate

        self.client.post(reverse('agents:document_create', args=[1]), ACT_DATA)
        loose = BirthCertificate.objects.get(request=None)
        url = reverse('agents:document_send', args=[1, loose.pk])
        self.client.post(url, {'message': ''})
        loose.refresh_from_db()
        self.assertIsNone(loose.sent_at)
        self.client.post(url, {'message': '', 'demande': self.dossier.pk})
        loose.refresh_from_db()
        self.assertEqual(loose.request, self.dossier)
        self.assertIsNotNone(loose.sent_at)

    def test_deleted_act_is_no_longer_downloadable(self):
        from django.utils import timezone

        self.client.post(self.send_url, {'message': ''})
        type(self.act).objects.filter(pk=self.act.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.api(self.download_url()).status_code, 404)

    def test_cannot_send_while_deletion_is_pending(self):
        self.client.post(reverse('agents:document_delete', args=[1, self.act.pk]), {'reason': 'Doublon'})
        self.client.post(self.send_url, {'message': ''})
        self.act.refresh_from_db()
        self.assertIsNone(self.act.sent_at)



# ---------------------------------------------------------------------------
# Guichets 2 à 5 : chaque guichet a son propre document officiel
# ---------------------------------------------------------------------------

REGISTRATION = {
    'region': 'Boeny', 'district': 'Mahajanga I', 'commune': 'Commune Urbaine de Mahajanga',
    'act_datetime': '2026-05-16T10:15', 'registrar_name': 'Hery RAKOTO',
}

DOCUMENT_CASES = {
    2: {
        'prefix': 'MAR', 'request_type': 'mariage',
        'request_details': {'spouse1_name': 'RABE Jean', 'spouse2_name': 'RASOA Lala',
                            'marriage_date': '2026-05-10', 'marriage_place': 'Hôtel de Ville'},
        'prefilled': 'RASOA Lala',
        'data': {
            **REGISTRATION, 'registrar_title': "Officier de l'état civil",
            'marriage_datetime': '2026-05-10T09:00', 'marriage_place': 'Hôtel de Ville de Mahajanga',
            'matrimonial_regime': 'Communauté de biens',
            'husband_last_name': 'Rabe', 'husband_first_names': 'Jean', 'husband_birth_date': '1990-01-01',
            'husband_birth_place': 'Mahajanga', 'husband_profession': 'enseignant', 'husband_address': 'Tsaramandroso',
            'husband_father_name': 'Paul RABE', 'husband_mother_name': 'Marie RASOA',
            'wife_last_name': 'Rasoa', 'wife_first_names': 'Lala', 'wife_birth_date': '1992-02-02',
            'wife_birth_place': 'Antananarivo', 'wife_profession': 'infirmière', 'wife_address': 'Mahabibo',
            'wife_father_name': '', 'wife_mother_name': 'Vola RASOA',
            'witness1_name': 'Tiana R.', 'witness1_details': 'commerçant', 'witness2_name': 'Fara R.',
            'witness2_details': '', 'marginal_notes': 'Sans objet.',
        },
        'bad': {'husband_birth_date': '2026-06-01'},  # né après le mariage
    },
    3: {
        'prefix': 'DEC', 'request_type': 'deces',
        'request_details': {'deceased_name': 'RAKOTO Be', 'death_date': '2026-04-01',
                            'death_place': 'CHU Mahajanga', 'relationship': 'child'},
        'prefilled': 'RAKOTO Be',
        'data': {
            **REGISTRATION, 'registrar_title': "Officier de l'état civil",
            'deceased_last_name': 'Rakoto', 'deceased_first_names': 'Be', 'deceased_sex': 'M',
            'deceased_birth_date': '1940-03-03', 'deceased_birth_place': 'Marovoay', 'deceased_profession': 'retraité',
            'deceased_address': 'Mahabibo', 'marital_status': 'WIDOWED', 'spouse_name': '',
            'father_name': '', 'mother_name': '', 'death_datetime': '2026-04-01T06:30', 'death_place': 'CHU Mahajanga',
            'declarant_name': 'Jean RAKOTO', 'declarant_relationship': 'fils du défunt', 'declarant_address': '',
            'marginal_notes': 'Sans objet.',
        },
        'bad': {'death_datetime': '2026-06-01T06:30'},  # acte dressé avant le décès
    },
    4: {
        'prefix': 'LEG', 'request_type': 'legislation',
        'request_details': {'text_type': 'arrete', 'reference_number': '012-CUM', 'subject': 'Horaires du marché'},
        'prefilled': '012-CUM',
        'data': {
            **REGISTRATION, 'registrar_title': 'Le Maire',
            'text_type': 'arrete', 'text_number': '012-CUM/2026', 'text_date': '2026-01-15',
            'subject': 'Réglementation des horaires du marché', 'content': 'Article 1 : …\nArticle 2 : …',
            'recipient_name': 'Jean RABE',
        },
        'bad': {'text_date': '2026-06-01'},  # texte postérieur à l'extrait
    },
    5: {
        'prefix': 'ATT', 'request_type': 'transport',
        'request_details': {'request_kind': 'licence', 'vehicle_type': 'taxi', 'vehicle_plate': '1234 TBA'},
        'prefilled': '1234 TBA',
        'data': {
            **REGISTRATION, 'registrar_title': 'Le Chef de service',
            'service': 'transport', 'nature': 'Licence de taxi', 'holder_full_name': 'RABE Jean',
            'holder_national_id': '501 011 012 013', 'holder_address': 'Tsaramandroso',
            'reference': '1234 TBA', 'location': '', 'subject': 'Exploitation d\'un taxi en ville.',
            'amount': '150000', 'valid_until': '2027-05-16', 'observations': '',
        },
        'bad': {'amount': '-5'},
    },
}


class OtherGuichetsDocumentsTests(TestCase):
    def setUp(self):
        from unittest import mock

        from django.core.cache import cache
        from espace.tests import fake_verify_token

        cache.clear()
        patcher = mock.patch('espace.auth.verify_clerk_token', side_effect=fake_verify_token)
        patcher.start()
        self.addCleanup(patcher.stop)
        for number in DOCUMENT_CASES:
            make_agent(f'agent{number}', number)

    def login(self, number):
        self.client.login(username=f'agent{number}', password=PASSWORD)

    def api(self, url):
        from django.test import override_settings
        from espace.tests import CLERK_SETTINGS

        with override_settings(**CLERK_SETTINGS):
            return self.client.get(url, HTTP_AUTHORIZATION='Bearer user_a')

    def test_each_guichet_issues_its_own_document(self):
        from .official import OFFICIAL_DOCUMENTS

        for number, case in DOCUMENT_CASES.items():
            with self.subTest(guichet=number):
                self.login(number)
                model = OFFICIAL_DOCUMENTS[number].model
                response = self.client.post(reverse('agents:document_create', args=[number]), case['data'])
                document = model.objects.get()
                self.assertRedirects(response, reverse('agents:document_detail', args=[number, document.pk]))
                self.assertEqual(document.act_number, f"2026-{case['prefix']}-00001")
                self.assertTrue(document.verify()['is_authentic'])

                self.assertContains(self.client.get(reverse('agents:folder_documents', args=[number])), document.act_number)
                self.assertContains(self.client.get(reverse('agents:document_detail', args=[number, document.pk])),
                                    document.content_hash)
                pdf = self.client.get(reverse('agents:document_pdf', args=[number, document.pk]))
                self.assertTrue(pdf.content.startswith(b'%PDF'))

                data = self.client.get(reverse('verify_document', args=[document.pk])).json()
                self.assertTrue(data['is_authentic'])
                self.assertEqual(data['document']['document_type'], model.DOCUMENT_CODE)

    def test_invalid_data_is_refused(self):
        from .official import OFFICIAL_DOCUMENTS

        for number, case in DOCUMENT_CASES.items():
            with self.subTest(guichet=number):
                self.login(number)
                response = self.client.post(
                    reverse('agents:document_create', args=[number]), {**case['data'], **case['bad']},
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(OFFICIAL_DOCUMENTS[number].model.objects.exists())

    def test_prefill_send_and_download(self):
        from .official import OFFICIAL_DOCUMENTS

        for number, case in DOCUMENT_CASES.items():
            with self.subTest(guichet=number):
                self.login(number)
                dossier = DossierRequest.objects.create(
                    clerk_user_id='user_a', dossier_type=case['request_type'],
                    identity={'last_name': 'RABE', 'first_name': 'Jean', 'email': 'jean@example.com'},
                    details=case['request_details'],
                )
                create_url = reverse('agents:document_create', args=[number])
                self.assertContains(self.client.get(f'{create_url}?demande={dossier.pk}'), case['prefilled'])
                self.assertContains(
                    self.client.get(reverse('agents:request_detail', args=[number, dossier.pk])),
                    OFFICIAL_DOCUMENTS[number].issue_label.replace("'", '&#x27;'),
                )

                self.client.post(create_url, {**case['data'], 'demande': dossier.pk})
                document = OFFICIAL_DOCUMENTS[number].model.objects.get(request=dossier)
                self.client.post(reverse('agents:document_send', args=[number, document.pk]), {'message': ''})
                dossier.refresh_from_db()
                self.assertEqual(dossier.status, DossierRequest.Status.COMPLETED)

                listed = {d['id'] for item in self.api(reverse('dossier_collection')).json()['results']
                          for d in item['documents']}
                self.assertIn(str(document.pk), listed)
                download = self.api(reverse('dossier_document', args=[dossier.pk, document.pk]))
                self.assertEqual(download.status_code, 200)
                self.assertTrue(download.content.startswith(b'%PDF'))

    def test_guichets_are_isolated(self):
        from .official import OFFICIAL_DOCUMENTS

        self.login(2)
        self.client.post(reverse('agents:document_create', args=[2]), DOCUMENT_CASES[2]['data'])
        marriage = OFFICIAL_DOCUMENTS[2].model.objects.get()
        self.login(5)
        self.assertEqual(self.client.get(reverse('agents:documents', args=[2])).status_code, 403)
        self.assertEqual(self.client.get(reverse('agents:document_detail', args=[2, marriage.pk])).status_code, 403)
        # Depuis son propre guichet, l'identifiant d'un acte de mariage est introuvable.
        self.assertEqual(self.client.get(reverse('agents:document_detail', args=[5, marriage.pk])).status_code, 404)

    def test_service_title_follows_the_service(self):
        from .models import ServiceCertificate

        self.login(5)
        self.client.post(reverse('agents:document_create', args=[5]), {**DOCUMENT_CASES[5]['data'], 'service': 'cadastre'})
        self.assertEqual(ServiceCertificate.objects.get().document_title, 'EXTRAIT CADASTRAL')

    def test_admin_cannot_hard_delete_documents(self):
        from .official import DOCUMENT_MODELS

        admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        self.client.force_login(admin_user)
        self.login(3)
        self.client.post(reverse('agents:document_create', args=[3]), DOCUMENT_CASES[3]['data'])
        self.client.force_login(admin_user)
        for model in DOCUMENT_MODELS:
            url = reverse(f'admin:agents_{model._meta.model_name}_changelist')
            self.assertEqual(self.client.get(url).status_code, 200)
        from .models import DeathCertificate

        death = DeathCertificate.objects.get()
        response = self.client.get(reverse('admin:agents_deathcertificate_delete', args=[death.pk]))
        self.assertEqual(response.status_code, 403)


class LateSealedFieldsTests(TestCase):
    """Champs ajoutés après coup : les anciens actes restent valides, une falsification reste détectée."""

    def setUp(self):
        make_agent('deces', 3)
        self.client.login(username='deces', password=PASSWORD)

    def test_new_fields_are_sealed_when_filled(self):
        from .models import DeathCertificate

        data = {**DOCUMENT_CASES[3]['data'], 'father_name': 'Koto RAKOTO', 'father_deceased': 'on',
                'declarant_age': '45', 'declarant_profession': 'ingénieur'}
        self.client.post(reverse('agents:document_create', args=[3]), data)
        act = DeathCertificate.objects.get()
        self.assertTrue(act.father_deceased)
        self.assertTrue(act.verify()['is_authentic'])
        DeathCertificate.objects.filter(pk=act.pk).update(declarant_age=30)  # falsification
        act.refresh_from_db()
        self.assertFalse(act.verify()['is_authentic'])

    def test_document_without_new_fields_keeps_its_hash(self):
        from .models import DeathCertificate

        self.client.post(reverse('agents:document_create', args=[3]), DOCUMENT_CASES[3]['data'])
        act = DeathCertificate.objects.get()
        payload = act.canonical_payload()
        for name in DeathCertificate.LATE_SEALED_FIELDS:
            self.assertNotIn(f'"{name}"', payload)
        self.assertTrue(act.verify()['is_authentic'])
        DeathCertificate.objects.filter(pk=act.pk).update(mother_deceased=True)  # ajout frauduleux
        act.refresh_from_db()
        self.assertFalse(act.verify()['is_authentic'])

    def test_age_at_death(self):
        from .models import DeathCertificate

        self.client.post(reverse('agents:document_create', args=[3]), DOCUMENT_CASES[3]['data'])
        self.assertEqual(DeathCertificate.objects.get().age_at_death, 86)  # né le 3 mars 1940, décédé le 1er avril 2026


class AdminMailPageTests(TestCase):
    """Page « Mail » de l'admin : sa boîte mail, avec toutes les personnes de l'application en suggestions."""

    def test_suggests_team_and_citizens(self):
        admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        agent = make_agent('naissance', 1)
        agent.email = 'agent1@example.com'
        agent.save()
        make_request('naissance')  # usager user_123, jean@example.com

        self.client.force_login(admin_user)
        response = self.client.get(reverse('admin:mail'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nouveau message')
        self.assertContains(response, '<option value="agent1@example.com">')
        self.assertContains(response, '<option value="jean@example.com">')
        self.assertNotContains(response, '<option value="chef@example.com">')  # pas soi-même

    def test_agents_cannot_open_it(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        self.assertNotEqual(self.client.get(reverse('admin:mail')).status_code, 200)


class QueueOrderTests(TestCase):
    """Premier arrivé, premier servi : la demande la plus ancienne d'un type se traite en premier."""

    def setUp(self):
        make_agent('mariage', 2)
        self.client.login(username='mariage', password=PASSWORD)
        self.first = make_request('mariage')
        self.later = [make_request('mariage') for _ in range(4)]

    def decide(self, dossier, status=DossierRequest.Status.IN_PROGRESS):
        return self.client.post(
            reverse('agents:request_detail', args=[2, dossier.pk]),
            {'status': status, 'response_message': ''},
        )

    def test_cannot_skip_the_first_request(self):
        fourth = self.later[2]
        response = self.decide(fourth)
        self.assertRedirects(response, reverse('agents:request_detail', args=[2, fourth.pk]))
        fourth.refresh_from_db()
        self.assertEqual(fourth.status, DossierRequest.Status.PENDING)
        message = str(list(get_messages(response.wsgi_request))[0])
        self.assertIn(self.first.reference, message)
        self.assertIn("d'abord traiter", message)

        page = self.client.get(reverse('agents:request_detail', args=[2, fourth.pk]))
        self.assertContains(page, 'agent-queue-alert')
        self.assertContains(page, reverse('agents:request_detail', args=[2, self.first.pk]))

    def test_order_is_followed(self):
        self.decide(self.first)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, DossierRequest.Status.IN_PROGRESS)
        # La deuxième devient traitable, la troisième attend toujours.
        self.decide(self.later[0])
        self.later[0].refresh_from_db()
        self.assertEqual(self.later[0].status, DossierRequest.Status.IN_PROGRESS)
        self.decide(self.later[2])
        self.later[2].refresh_from_db()
        self.assertEqual(self.later[2].status, DossierRequest.Status.PENDING)

    def test_cannot_issue_document_out_of_order(self):
        url = reverse('agents:document_create', args=[2]) + f'?demande={self.later[0].pk}'
        self.assertRedirects(self.client.get(url), reverse('agents:request_detail', args=[2, self.later[0].pk]))
        self.assertEqual(self.client.get(reverse('agents:document_create', args=[2]) + f'?demande={self.first.pk}').status_code, 200)

    def test_list_shows_queue_position(self):
        response = self.client.get(reverse('agents:requests', args=[2]))
        self.assertContains(response, 'À traiter en premier', count=1)
        self.assertContains(response, 'N° 5 dans la file')

    def test_each_type_has_its_own_queue(self):
        make_agent('recette', 5)
        self.client.login(username='recette', password=PASSWORD)
        make_request('recette')
        transport = make_request('transport')  # plus récente, mais seule de son type
        self.client.post(
            reverse('agents:request_detail', args=[5, transport.pk]),
            {'status': DossierRequest.Status.IN_PROGRESS, 'response_message': ''},
        )
        transport.refresh_from_db()
        self.assertEqual(transport.status, DossierRequest.Status.IN_PROGRESS)


class AssistantTests(TestCase):
    """Assistant IA local : questions sur l'application et actions confirmées, dans le périmètre du compte."""

    def setUp(self):
        make_agent('mariage', 2)
        self.client.login(username='mariage', password=PASSWORD)
        self.first = make_request('mariage')  # RABE Jean
        self.second = make_request('mariage')
        self.second.identity = {'last_name': 'RAKOTO', 'first_name': 'Hery'}
        self.second.save()
        self.url = reverse('agents:assistant')

    def ask(self, message, page=''):
        response = self.client.post(self.url, {'message': message, 'page': page}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_help_and_out_of_scope(self):
        self.assertIn('Exemples', self.ask('aide')['text'])
        self.assertIn('Je ne peux pas', self.ask('Quelle est la météo à Paris ?')['text'])

    def test_next_request_question(self):
        data = self.ask('Quelle est la prochaine demande à traiter ?')
        self.assertIn(self.first.reference, data['items'][0]['label'])
        self.assertIsNone(data['confirm'])

    def test_action_needs_confirmation_then_runs(self):
        data = self.ask('Peux-tu prendre en charge la prochaine demande à ma place ?')
        self.assertEqual(data['confirm']['pk'], self.first.pk)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, DossierRequest.Status.PENDING)  # rien sans confirmation

        done = self.client.post(self.url, {'confirm': data['confirm']}, content_type='application/json').json()
        self.assertIn("C'est fait", done['text'])
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, DossierRequest.Status.IN_PROGRESS)

    def test_refusal_with_reason_by_name(self):
        data = self.ask('Refuse la demande de Rabe motif : pièce manquante')
        self.assertEqual(data['confirm']['status'], DossierRequest.Status.REJECTED)
        self.assertEqual(data['confirm']['message'], 'pièce manquante')

    def test_respects_queue_order(self):
        page = reverse('agents:request_detail', args=[2, self.second.pk])
        data = self.ask('Peux-tu faire cette demande à ma place', page=page)
        self.assertIsNone(data['confirm'])
        self.assertIn(self.first.reference, data['text'])
        # Même une confirmation forgée est refusée.
        forged = {'action': 'status', 'pk': self.second.pk, 'status': 'APPROVED', 'message': ''}
        self.client.post(self.url, {'confirm': forged}, content_type='application/json')
        self.second.refresh_from_db()
        self.assertEqual(self.second.status, DossierRequest.Status.PENDING)

    def test_agent_cannot_reach_other_guichet(self):
        other = make_request('naissance')
        data = self.ask(f'Montre la demande {other.reference}')
        self.assertIn('Je ne trouve pas', data['text'])
        forged = {'action': 'status', 'pk': other.pk, 'status': 'APPROVED', 'message': ''}
        self.client.post(self.url, {'confirm': forged}, content_type='application/json')
        other.refresh_from_db()
        self.assertEqual(other.status, DossierRequest.Status.PENDING)

    def test_stats_and_admin_scope(self):
        self.assertIn('2 au total', self.ask('Combien de demandes ?')['text'])
        admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        self.client.force_login(admin_user)
        make_request('naissance')
        self.assertIn('3 au total', self.ask('combien de demandes ?')['text'])
        self.assertIn('contrôlé', self.ask('Y a-t-il des fraudes ?')['text'])

    def test_widget_in_sidebars(self):
        self.assertContains(self.client.get(reverse('agents:dashboard', args=[2])), 'id="assistant-toggle"')
        admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        self.client.force_login(admin_user)
        self.assertContains(self.client.get(reverse('admin:index')), 'id="assistant-toggle"')

    def test_requires_login(self):
        self.client.logout()
        response = self.client.post(self.url, {'message': 'aide'}, content_type='application/json')
        self.assertEqual(response.status_code, 302)


class AdminSecurityPageTests(TestCase):
    """Page « Sécurité et fraude » : documents des agents re-vérifiés, altérations signalées."""

    def setUp(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        self.client.post(reverse('agents:document_create', args=[1]), ACT_DATA)
        self.client.logout()
        self.admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)

    def test_flags_altered_document(self):
        from .models import BirthCertificate

        act = BirthCertificate.objects.get()
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin:security'))
        self.assertContains(response, act.act_number)
        self.assertContains(response, 'Intègre')
        self.assertNotContains(response, 'Altéré — fraude')

        # Modification en base, hors de l'application : l'empreinte ne correspond plus.
        BirthCertificate.objects.filter(pk=act.pk).update(child_last_name='Faux')
        altered = self.client.get(reverse('admin:security') + '?vue=alteres')
        self.assertContains(altered, act.act_number)
        self.assertContains(altered, 'Altéré — fraude')

    def test_in_sidebar_instead_of_contact_messages(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, reverse('admin:security'))
        self.assertNotContains(response, 'Messages de contact</span>')

    def test_agents_cannot_open_it(self):
        self.client.login(username='naissance', password=PASSWORD)
        self.assertNotEqual(self.client.get(reverse('admin:security')).status_code, 200)


class AdminLogoutTests(TestCase):
    def test_admin_logout_goes_to_home(self):
        admin_user = get_user_model().objects.create_superuser('chef', 'chef@example.com', PASSWORD)
        self.client.force_login(admin_user)
        response = self.client.post(reverse('admin:logout'))
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('_auth_user_id', self.client.session)


class QuartierOnAgentPagesTests(TestCase):
    """Fokontany et résidence principale : bloc « Quartier » de la fiche, colonne et filtre de la liste."""

    def setUp(self):
        make_agent('naissance', 1)
        self.client.login(username='naissance', password=PASSWORD)
        self.here = make_request('naissance', details={'copies': '1', 'fokontany': 'Mahabibo', 'main_residence': 'non'})
        self.other = make_request('naissance', details={'copies': '1', 'fokontany': 'Amborovy', 'main_residence': 'oui'})

    def test_detail_shows_quartier_block(self):
        response = self.client.get(reverse('agents:request_detail', args=[1, self.here.pk]))
        self.assertContains(response, '<h2>Quartier</h2>', html=True)
        self.assertContains(response, '<dt>Résidence principale</dt><dd>Non</dd>', html=True)

    def test_list_filters_by_fokontany(self):
        url = reverse('agents:requests', args=[1])
        response = self.client.get(f'{url}?fokontany=Mahabibo')
        self.assertContains(response, self.here.reference)
        self.assertNotContains(response, self.other.reference)
        self.assertContains(self.client.get(url), self.other.reference)
