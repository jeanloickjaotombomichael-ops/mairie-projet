import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agents.models import AgentProfile

from .models import Folder, StoredFile

PASSWORD = 'motdepasse-solide-123'
MEDIA = tempfile.mkdtemp()


def make_agent(username, guichet):
    user = get_user_model().objects.create_user(username, password=PASSWORD)
    AgentProfile.objects.create(user=user, guichet=guichet)
    return user


@override_settings(MEDIA_ROOT=MEDIA)
class FoldersTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.agent = make_agent('naissance', 1)
        self.client.force_login(self.agent)
        self.url = reverse('agents:folders', args=[1])
        self.trash_url = reverse('agents:trash', args=[1])

    def upload(self, folder=None, name='note.txt'):
        url = f'{self.url}?d={folder.pk}' if folder else self.url
        self.client.post(url, {'action': 'upload', 'files': SimpleUploadedFile(name, b'bonjour', 'text/plain')})
        return StoredFile.objects.latest('pk')

    def test_create_folder_and_upload(self):
        self.client.post(self.url, {'action': 'create_folder', 'name': 'Archives 2026'})
        folder = Folder.objects.get(owner=self.agent)
        item = self.upload(folder)
        self.assertEqual(item.folder, folder)
        self.assertEqual(item.size, 7)
        self.assertContains(self.client.get(f'{self.url}?d={folder.pk}'), 'note.txt')
        response = self.client.get(reverse('agents:file_open', args=[1, item.pk]))
        self.assertEqual(b''.join(response.streaming_content), b'bonjour')

    def test_other_agent_sees_nothing(self):
        folder = Folder.objects.create(owner=self.agent, name='Privé')
        item = self.upload(folder)
        other = make_agent('naissance2', 1)  # même guichet, autre agent
        self.client.force_login(other)
        self.assertNotContains(self.client.get(self.url), 'Privé')
        self.assertEqual(self.client.get(reverse('agents:file_open', args=[1, item.pk])).status_code, 404)
        self.client.post(self.url, {'action': 'trash_folder', 'id': folder.pk})
        folder.refresh_from_db()
        self.assertIsNone(folder.trashed_at)
        self.assertNotContains(self.client.get(self.trash_url), 'Privé')

    def test_trash_restore_and_delete(self):
        folder = Folder.objects.create(owner=self.agent, name='Brouillons')
        item = self.upload(folder)
        self.client.post(self.url, {'action': 'trash_folder', 'id': folder.pk})
        self.assertNotContains(self.client.get(self.url), '<strong>Brouillons</strong>')
        self.assertContains(self.client.get(self.trash_url), '<strong>Brouillons</strong>')
        # Son contenu n'est plus accessible tant que le dossier est dans la corbeille.
        self.assertEqual(self.client.get(reverse('agents:file_open', args=[1, item.pk])).status_code, 404)

        self.client.post(self.trash_url, {'action': 'restore_folder', 'id': folder.pk})
        self.assertContains(self.client.get(f'{self.url}?d={folder.pk}'), 'note.txt')

        self.client.post(self.url, {'action': 'trash_file', 'id': item.pk})
        path = item.file.path
        self.client.post(self.trash_url, {'action': 'delete_file', 'id': item.pk})
        self.assertFalse(StoredFile.objects.filter(pk=item.pk).exists())
        self.assertFalse(os.path.exists(path))  # supprimé du disque aussi

    def test_restored_file_goes_to_root_when_its_folder_is_in_trash(self):
        folder = Folder.objects.create(owner=self.agent, name='A')
        item = self.upload(folder)
        StoredFile.objects.filter(pk=item.pk).update(trashed_at=timezone.now())
        Folder.objects.filter(pk=folder.pk).update(trashed_at=timezone.now())
        self.client.post(self.trash_url, {'action': 'restore_file', 'id': item.pk})
        item.refresh_from_db()
        self.assertIsNone(item.folder)
        self.assertIsNone(item.trashed_at)

    def test_old_trash_is_purged_and_badge(self):
        Folder.objects.create(owner=self.agent, name='Vieux', trashed_at=timezone.now() - timezone.timedelta(days=31))
        Folder.objects.create(owner=self.agent, name='Récent', trashed_at=timezone.now())
        response = self.client.get(self.trash_url)
        self.assertNotContains(response, 'Vieux')
        self.assertContains(response, 'Récent')
        self.assertContains(response, 'Corbeille</span>\n            <span class="mairy-count">1</span>')
