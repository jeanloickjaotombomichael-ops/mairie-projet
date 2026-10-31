"""Pages « Dossiers » et « Corbeille » de l'espace agent. Chaque requête est filtrée sur l'agent connecté."""
import datetime
import mimetypes

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext as _

from agents.access import guichet_required
from agents.views import _shell

from .models import Folder, StoredFile

TRASH_DAYS = 30
MAX_FILE_SIZE = 25 * 1024 * 1024
# Types affichés dans le navigateur ; tout le reste est téléchargé.
INLINE_TYPES = {'application/pdf', 'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'text/plain'}


def _purge(user):
    # La corbeille se vide d'elle-même au bout de 30 jours.
    limit = timezone.now() - datetime.timedelta(days=TRASH_DAYS)
    for item in StoredFile.objects.filter(owner=user, trashed_at__lt=limit):
        item.delete()
    for folder in Folder.objects.filter(owner=user, trashed_at__lt=limit):
        folder.delete()


def _clean_name(raw, limit):
    return ' '.join(raw.replace('/', '-').replace('\\', '-').split())[:limit]


def _folder_url(number, folder):
    url = reverse('agents:folders', args=[number])
    return f'{url}?{urlencode({"d": folder.pk})}' if folder else url


@guichet_required
def folders(request, number):
    user = request.user
    current = None
    if request.GET.get('d', '').isdigit():
        current = Folder.objects.filter(owner=user, pk=request.GET['d']).select_related('parent').first()
        if current is None or not current.is_reachable():
            return redirect('agents:folders', number)

    if request.method == 'POST':
        _handle_folder_post(request, current)
        return redirect(_folder_url(number, current))

    _purge(user)
    query = request.GET.get('q', '').strip()
    if query:
        subfolders = [f for f in Folder.objects.filter(owner=user, trashed_at=None, name__icontains=query)
                      if f.is_reachable()]
        files = [f for f in StoredFile.objects.filter(owner=user, trashed_at=None, name__icontains=query)
                 .select_related('folder') if f.is_reachable()]
    else:
        subfolders = list(Folder.objects.filter(owner=user, parent=current, trashed_at=None))
        files = list(StoredFile.objects.filter(owner=user, folder=current, trashed_at=None))
    for folder in subfolders:
        folder.url = _folder_url(number, folder)
        folder.count = folder.children.filter(trashed_at=None).count() + folder.files.filter(trashed_at=None).count()

    context = {
        **_shell(request, number, 'folders'),
        'title': current.name if current else _('Dossiers'),
        'current': current,
        'breadcrumb': [{'name': f.name, 'url': _folder_url(number, f)} for f in current.ancestors()] if current else [],
        'subfolders': subfolders,
        'files': files,
        'query': query,
        'max_size_mb': MAX_FILE_SIZE // (1024 * 1024),
    }
    return render(request, 'agents/dossiers.html', context)


def _handle_folder_post(request, current):
    user = request.user
    action = request.POST.get('action', '')
    pk = request.POST.get('id', '')
    pk = int(pk) if pk.isdigit() else 0

    if action == 'create_folder':
        name = _clean_name(request.POST.get('name', ''), 120)
        if name:
            Folder.objects.create(owner=user, parent=current, name=name)
            messages.success(request, _('Dossier « %(name)s » créé.') % {'name': name})
    elif action == 'upload':
        added, refused = 0, []
        for upload in request.FILES.getlist('files'):
            if upload.size > MAX_FILE_SIZE:
                refused.append(upload.name)
                continue
            StoredFile.objects.create(
                owner=user, folder=current, name=_clean_name(upload.name, 255) or 'fichier', file=upload,
                size=upload.size, content_type=(upload.content_type or '')[:120],
            )
            added += 1
        if added:
            messages.success(request, _('%(count)s fichier(s) importé(s).') % {'count': added})
        if refused:
            messages.error(request, _('Trop volumineux (plus de %(size)s Mo) : %(names)s') % {
                'size': MAX_FILE_SIZE // (1024 * 1024), 'names': ', '.join(refused),
            })
    elif action in ('rename_folder', 'rename_file'):
        model = Folder if action == 'rename_folder' else StoredFile
        item = get_object_or_404(model, owner=user, pk=pk, trashed_at=None)
        name = _clean_name(request.POST.get('name', ''), 120 if model is Folder else 255)
        if name:
            item.name = name
            item.save(update_fields=['name'])
    elif action in ('trash_folder', 'trash_file'):
        model = Folder if action == 'trash_folder' else StoredFile
        item = get_object_or_404(model, owner=user, pk=pk, trashed_at=None)
        item.trashed_at = timezone.now()
        item.save(update_fields=['trashed_at'])
        messages.info(request, _('« %(name)s » a été placé dans la corbeille.') % {'name': item.name})


@guichet_required
def file_open(request, number, pk):
    item = get_object_or_404(StoredFile, owner=request.user, pk=pk)
    if not item.is_reachable():
        raise Http404
    content_type = item.content_type or mimetypes.guess_type(item.name)[0] or 'application/octet-stream'
    inline = request.GET.get('voir') == '1' and content_type in INLINE_TYPES
    try:
        handle = item.file.open('rb')
    except FileNotFoundError:
        raise Http404
    return FileResponse(handle, as_attachment=not inline, filename=item.name, content_type=content_type)


@guichet_required
def trash(request, number):
    user = request.user
    if request.method == 'POST':
        _handle_trash_post(request)
        return redirect('agents:trash', number)

    _purge(user)
    items = []
    for folder in Folder.objects.filter(owner=user).exclude(trashed_at=None).select_related('parent'):
        items.append({'kind': 'folder', 'obj': folder, 'parent': folder.parent})
    for item in StoredFile.objects.filter(owner=user).exclude(trashed_at=None).select_related('folder'):
        items.append({'kind': 'file', 'obj': item, 'parent': item.folder})
    for entry in items:
        entry['expires'] = entry['obj'].trashed_at + datetime.timedelta(days=TRASH_DAYS)
        parent = entry['parent']
        entry['location'] = ' / '.join(f.name for f in parent.ancestors()) if parent else _('Dossiers')
    items.sort(key=lambda entry: entry['obj'].trashed_at, reverse=True)

    context = {
        **_shell(request, number, 'trash'),
        'title': _('Corbeille'),
        'items': items,
        'trash_days': TRASH_DAYS,
    }
    return render(request, 'agents/corbeille.html', context)


def _handle_trash_post(request):
    user = request.user
    action = request.POST.get('action', '')
    pk = request.POST.get('id', '')
    pk = int(pk) if pk.isdigit() else 0

    if action == 'empty':
        for item in StoredFile.objects.filter(owner=user).exclude(trashed_at=None):
            item.delete()
        for folder in Folder.objects.filter(owner=user).exclude(trashed_at=None):
            folder.delete()
        messages.info(request, _('La corbeille a été vidée.'))
        return

    model = Folder if action.endswith('_folder') else StoredFile
    item = get_object_or_404(model, owner=user, pk=pk, trashed_at__isnull=False)
    if action.startswith('restore_'):
        item.trashed_at = None
        # Son dossier d'origine est lui-même dans la corbeille : il revient à la racine.
        parent_field = 'parent' if model is Folder else 'folder'
        parent = getattr(item, parent_field)
        moved = parent is not None and not parent.is_reachable()
        if moved:
            setattr(item, parent_field, None)
        item.save()
        if moved:
            messages.success(request, _('« %(name)s » a été restauré dans « Dossiers » (son dossier d\'origine est dans '
                                        'la corbeille).') % {'name': item.name})
        else:
            messages.success(request, _('« %(name)s » a été restauré.') % {'name': item.name})
    elif action.startswith('delete_'):
        name = item.name
        item.delete()
        messages.info(request, _('« %(name)s » a été supprimé définitivement.') % {'name': name})
