from django.contrib.auth import get_user_model
from django.core import mail as outbox
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agents.models import AgentProfile

from .models import Label, Mail

PASSWORD = 'motdepasse-solide-123'


class MailboxTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser('chef', 'chef@example.com', PASSWORD, first_name='Chef')
        self.agent = User.objects.create_user('naissance', 'agent1@example.com', PASSWORD)
        AgentProfile.objects.create(user=self.agent, guichet=1)
        self.admin_url = reverse('admin:mail')
        self.agent_url = reverse('agents:mail', args=[1])

    def send(self, url, follow=False, **data):
        return self.client.post(url, {'action': 'send', 'subject': 'Bonjour', 'body': 'Texte', **data}, follow=follow)

    def test_team_message_lands_in_inbox_unread(self):
        self.client.force_login(self.admin)
        self.send(self.admin_url, to='agent1@example.com')
        self.assertTrue(Mail.objects.filter(owner=self.admin, folder=Mail.Folder.SENT, subject='Bonjour').exists())
        received = Mail.objects.get(owner=self.agent, folder=Mail.Folder.INBOX)
        self.assertFalse(received.is_read)
        self.assertEqual(received.sender_email, 'chef@example.com')
        self.assertEqual(len(outbox.outbox), 0)  # compte de l'équipe : pas d'e-mail extérieur

        self.client.force_login(self.agent)
        response = self.client.get(self.agent_url)
        self.assertContains(response, 'Bonjour')
        self.assertContains(response, 'gm-row is-unread')
        self.client.get(f'{self.agent_url}?m={received.pk}')
        received.refresh_from_db()
        self.assertTrue(received.is_read)

    def test_external_address_without_smtp_is_kept_and_reported(self):
        self.client.force_login(self.agent)
        response = self.send(self.agent_url, to='usager@example.com', follow=True)
        self.assertContains(response, 'EMAIL_HOST')
        self.assertEqual(len(outbox.outbox), 0)
        self.assertTrue(Mail.objects.filter(owner=self.agent, folder=Mail.Folder.SENT).exists())

    @override_settings(EMAIL_HOST='smtp.example.com', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_external_address_gets_a_real_email(self):
        self.client.force_login(self.agent)
        self.send(self.agent_url, to='usager@example.com')
        self.assertEqual(len(outbox.outbox), 1)
        self.assertEqual(outbox.outbox[0].to, ['usager@example.com'])
        self.assertEqual(outbox.outbox[0].reply_to, ['agent1@example.com'])

    def test_invalid_recipient_keeps_a_draft(self):
        self.client.force_login(self.agent)
        self.send(self.agent_url, to='pas-une-adresse')
        draft = Mail.objects.get(owner=self.agent)
        self.assertEqual(draft.folder, Mail.Folder.DRAFT)
        self.assertContains(self.client.get(f'{self.agent_url}?f=drafts'), 'Brouillon')

    def test_trash_undo_and_empty(self):
        mail = Mail.objects.create(owner=self.agent, subject='A jeter')
        other = Mail.objects.create(owner=self.admin, subject='Pas à moi')
        self.client.force_login(self.agent)
        self.client.post(self.agent_url, {'op': 'trash', 'ids': [mail.pk, other.pk]})
        mail.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(mail.trashed_at)
        self.assertIsNone(other.trashed_at)  # message d'un autre : inchangé

        response = self.client.get(self.agent_url)
        self.assertContains(response, '1 conversation placée dans la corbeille.')
        self.assertNotContains(response, 'A jeter')
        self.client.post(self.agent_url, {'op': 'restore', 'ids': [mail.pk]})
        mail.refresh_from_db()
        self.assertIsNone(mail.trashed_at)

        Mail.objects.filter(pk=mail.pk).update(trashed_at=timezone.now())
        self.client.post(self.agent_url, {'action': 'empty_trash'})
        self.assertFalse(Mail.objects.filter(pk=mail.pk).exists())

    def test_star_snooze_and_labels(self):
        mail = Mail.objects.create(owner=self.agent, subject='Dossier X')
        self.client.force_login(self.agent)
        self.client.post(self.agent_url, {'toggle_star': mail.pk})
        self.assertContains(self.client.get(f'{self.agent_url}?f=starred'), 'Dossier X')

        self.client.post(self.agent_url, {'op': 'snooze:tomorrow', 'ids': [mail.pk]})
        self.assertNotContains(self.client.get(self.agent_url), 'Dossier X')
        self.assertContains(self.client.get(f'{self.agent_url}?f=snoozed'), 'Dossier X')

        self.client.post(self.agent_url, {'action': 'create_label', 'name': 'Urgent'})
        label = Label.objects.get(owner=self.agent)
        self.client.post(self.agent_url, {'op': f'label:{label.pk}', 'ids': [mail.pk]})
        self.assertContains(self.client.get(f'{self.agent_url}?f=label&l={label.pk}'), 'Dossier X')

    def test_reply_prefills_compose(self):
        mail = Mail.objects.create(owner=self.agent, subject='Question', sender_email='chef@example.com', body='Ligne')
        self.client.force_login(self.agent)
        response = self.client.get(f'{self.agent_url}?m={mail.pk}&compose=new&reply={mail.pk}')
        self.assertContains(response, 'value="Re: Question"')
        self.assertContains(response, 'value="chef@example.com"')
        self.assertContains(response, '&gt; Ligne')

    def test_unread_badge_in_menu(self):
        Mail.objects.create(owner=self.agent, subject='Nouveau', is_read=False)
        self.client.force_login(self.agent)
        response = self.client.get(reverse('agents:dashboard', args=[1]))
        self.assertContains(response, '<span class="mairy-count">1</span>', html=False)
