"""Page « Mail » partagée par l'administration et l'espace agent : dossiers, lecture, rédaction, libellés."""
import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .models import Label, Mail

PER_PAGE = 50
TRASH_DAYS = 30

# Dossiers du menu : (clé, libellé, icône). Les trois derniers sont repliés sous « Plus », comme dans Gmail.
FOLDERS = [
    ('inbox', gettext_lazy('Boîte de réception'), 'inbox'),
    ('starred', gettext_lazy('Messages suivis'), 'star'),
    ('snoozed', gettext_lazy('En attente'), 'clock'),
    ('sent', gettext_lazy('Messages envoyés'), 'send'),
    ('drafts', gettext_lazy('Brouillons'), 'draft'),
]
MORE_FOLDERS = [
    ('important', gettext_lazy('Importants'), 'important'),
    ('all', gettext_lazy('Tous les messages'), 'mail'),
    ('trash', gettext_lazy('Corbeille'), 'trash'),
]
FOLDER_LABELS = {key: label for key, label, _icon in FOLDERS + MORE_FOLDERS}


def unread_count(user):
    """Messages non lus de la boîte de réception (badge du menu latéral)."""
    return _folder_queryset(user, 'inbox').filter(is_read=False).count()


def _folder_queryset(user, key, label=None):
    now = timezone.now()
    mails = Mail.objects.filter(owner=user)
    if key == 'trash':
        return mails.exclude(trashed_at=None)
    mails = mails.filter(trashed_at=None)
    not_snoozed = Q(snoozed_until=None) | Q(snoozed_until__lte=now)
    if key == 'starred':
        return mails.filter(is_starred=True)
    if key == 'snoozed':
        return mails.filter(snoozed_until__gt=now)
    if key == 'sent':
        return mails.filter(folder=Mail.Folder.SENT)
    if key == 'drafts':
        return mails.filter(folder=Mail.Folder.DRAFT)
    if key == 'important':
        return mails.filter(is_important=True).exclude(folder=Mail.Folder.DRAFT)
    if key == 'all':
        return mails.exclude(folder=Mail.Folder.DRAFT)
    if key == 'label':
        return mails.filter(labels=label)
    return mails.filter(not_snoozed, folder=Mail.Folder.INBOX)


def _snooze_until(choice):
    now = timezone.localtime()
    morning = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if choice == 'tomorrow':
        return morning + datetime.timedelta(days=1)
    if choice == 'weekend':
        return morning + datetime.timedelta(days=(5 - now.weekday()) % 7 or 7)
    if choice == 'nextweek':
        return morning + datetime.timedelta(days=7 - now.weekday())
    return now + datetime.timedelta(hours=3)


def _short_date(value):
    local = timezone.localtime(value)
    now = timezone.localtime()
    if local.date() == now.date():
        return local.strftime('%H:%M')
    if local.year == now.year:
        return date_format(local, 'j M')
    return local.strftime('%d/%m/%Y')


def _parse_recipients(raw):
    addresses, invalid = [], []
    for item in raw.replace(';', ',').split(','):
        item = item.strip()
        if not item:
            continue
        try:
            validate_email(item)
        except ValidationError:
            invalid.append(item)
        else:
            if item.lower() not in (a.lower() for a in addresses):
                addresses.append(item)
    return addresses, invalid


def service_for(user):
    """Guichet de l'agent (« 1 » à « 5 »), ou « mairie » pour l'administration."""
    profile = getattr(user, 'agent_profile', None)
    return str(profile.guichet) if profile is not None else 'mairie'


def _send(request, to, subject, body, citizen=''):
    """
    Envoie le message : copie « envoyée » chez l'expéditeur, copie « reçue » chez les comptes de l'équipe.
    En réponse à un usager (``citizen``), une copie arrive aussi dans son espace usager.
    """
    user = request.user
    sender_name = user.get_full_name() or user.get_username()
    sender_email = user.email or settings.DEFAULT_FROM_EMAIL
    now = timezone.now()
    Mail.objects.create(
        owner=user, folder=Mail.Folder.SENT, sender_name=sender_name, sender_email=sender_email,
        to=', '.join(to), subject=subject, body=body, created_at=now, citizen_id=citizen,
    )

    in_space = set()
    if citizen:
        Mail.objects.create(
            owner=None, citizen_id=citizen, service=service_for(user), folder=Mail.Folder.INBOX,
            sender_name=sender_name, sender_email=sender_email, to=', '.join(to), subject=subject, body=body,
            created_at=now, is_read=False,
        )
        in_space = {
            email.lower() for email in Mail.objects.filter(owner=None, citizen_id=citizen, folder=Mail.Folder.SENT)
            .values_list('sender_email', flat=True)
        }

    external = []
    for address in to:
        accounts = list(get_user_model().objects.filter(email__iexact=address, is_active=True))
        for account in accounts:
            Mail.objects.create(
                owner=account, folder=Mail.Folder.INBOX, sender_name=sender_name, sender_email=sender_email,
                to=', '.join(to), subject=subject, body=body, created_at=now, is_read=False,
            )
        if not accounts:
            external.append(address)

    if not settings.EMAIL_HOST:
        # Sans serveur d'envoi, l'usager le lit quand même dans son espace.
        external = [address for address in external if address.lower() not in in_space]
    if not external:
        messages.success(request, _('Message envoyé.'))
        return
    if not settings.EMAIL_HOST:
        messages.warning(request, _(
            "Message enregistré dans « Messages envoyés », mais pas envoyé à %(to)s : aucun serveur d'envoi "
            "(EMAIL_HOST) n'est configuré."
        ) % {'to': ', '.join(external)})
        return
    try:
        EmailMessage(
            subject=subject, body=body, from_email=f'{sender_name} <{settings.DEFAULT_FROM_EMAIL}>',
            to=external, reply_to=[sender_email] if user.email else None,
        ).send()
    except Exception as error:  # serveur injoignable, identifiants refusés…
        messages.error(request, _("Le message n'a pas pu être envoyé à %(to)s (%(error)s).") % {
            'to': ', '.join(external), 'error': error,
        })
    else:
        messages.success(request, _('Message envoyé.'))


def _citizen(user, post):
    """Usager auquel on répond : seulement s'il a déjà écrit à cet utilisateur."""
    citizen = post.get('citizen', '').strip()[:100]
    if citizen and Mail.objects.filter(owner=user, citizen_id=citizen).exists():
        return citizen
    return ''


def _save_draft(user, post):
    draft = Mail.objects.filter(owner=user, folder=Mail.Folder.DRAFT, pk=post.get('draft') or 0).first()
    if draft is None:
        draft = Mail(owner=user, folder=Mail.Folder.DRAFT)
    draft.sender_name = user.get_full_name() or user.get_username()
    draft.sender_email = user.email
    draft.to = post.get('to', '').strip()[:1000]
    draft.subject = post.get('subject', '').strip()[:255]
    draft.body = post.get('body', '')
    draft.citizen_id = _citizen(user, post)
    draft.created_at = timezone.now()
    draft.save()
    return draft


def _handle_post(request):
    """Traite une action ; renvoie la chaîne de requête (GET) de la page à afficher ensuite."""
    user = request.user
    post = request.POST
    back = post.get('back', '')
    action = post.get('action', '')

    if action in ('send', 'draft', 'discard'):
        has_content = any(post.get(f, '').strip() for f in ('to', 'subject', 'body'))
        if action == 'discard':
            Mail.objects.filter(owner=user, folder=Mail.Folder.DRAFT, pk=post.get('draft') or 0).delete()
            messages.info(request, _('Brouillon supprimé.'))
        elif action == 'draft':
            if has_content:
                _save_draft(user, post)
                messages.info(request, _('Brouillon enregistré.'))
        else:
            to, invalid = _parse_recipients(post.get('to', ''))
            if invalid or not to:
                draft = _save_draft(user, post)
                messages.error(request, _('Adresse invalide : %(list)s') % {'list': ', '.join(invalid)} if invalid
                               else _('Indiquez au moins un destinataire.'))
                return urlencode({'f': 'drafts', 'compose': draft.pk})
            _send(request, to, post.get('subject', '').strip()[:255], post.get('body', ''), _citizen(user, post))
            Mail.objects.filter(owner=user, folder=Mail.Folder.DRAFT, pk=post.get('draft') or 0).delete()
        return back

    if action == 'create_label':
        name = post.get('name', '').strip()[:60]
        if name:
            label, _created = Label.objects.get_or_create(owner=user, name=name)
            return urlencode({'f': 'label', 'l': label.pk})
        return back
    if action == 'delete_label':
        Label.objects.filter(owner=user, pk=post.get('label') or 0).delete()
        return ''
    if action == 'empty_trash':
        Mail.objects.filter(owner=user).exclude(trashed_at=None).delete()
        messages.info(request, _('La corbeille a été vidée.'))
        return back

    if post.get('toggle_star'):
        mail = get_object_or_404(Mail, owner=user, pk=post['toggle_star'])
        mail.is_starred = not mail.is_starred
        mail.save(update_fields=['is_starred'])
        return back
    if post.get('toggle_important'):
        mail = get_object_or_404(Mail, owner=user, pk=post['toggle_important'])
        mail.is_important = not mail.is_important
        mail.save(update_fields=['is_important'])
        return back

    # Actions groupées sur les messages cochés.
    selected = Mail.objects.filter(owner=user, pk__in=[pk for pk in post.getlist('ids') if pk.isdigit()])
    count = selected.count()
    op = post.get('op', '')
    if not count:
        if op:
            messages.info(request, _('Aucun message sélectionné.'))
        return back
    if op == 'trash':
        ids = list(selected.values_list('pk', flat=True))
        selected.update(trashed_at=timezone.now())
        request.session['mail_undo'] = {'ids': ids, 'back': back}
    elif op == 'restore':
        selected.update(trashed_at=None)
        messages.info(request, _('%(count)s conversation(s) restaurée(s).') % {'count': count})
    elif op == 'delete':
        selected.exclude(trashed_at=None).delete()
        messages.info(request, _('%(count)s conversation(s) supprimée(s) définitivement.') % {'count': count})
    elif op in ('read', 'unread'):
        selected.update(is_read=op == 'read')
    elif op in ('star', 'unstar'):
        selected.update(is_starred=op == 'star')
    elif op in ('important', 'unimportant'):
        selected.update(is_important=op == 'important')
    elif op == 'unsnooze':
        selected.update(snoozed_until=None)
    elif op.startswith('snooze:'):
        until = _snooze_until(op.split(':', 1)[1])
        selected.update(snoozed_until=until)
        messages.info(request, _("%(count)s conversation(s) mise(s) en attente jusqu'au %(date)s.") % {
            'count': count, 'date': timezone.localtime(until).strftime('%d/%m/%Y %H:%M'),
        })
    elif op.startswith('label:') or op.startswith('unlabel:'):
        kind, _sep, pk = op.partition(':')
        label = get_object_or_404(Label, owner=user, pk=pk if pk.isdigit() else 0)
        for mail in selected:
            (mail.labels.add if kind == 'label' else mail.labels.remove)(label)
    return back


def mailbox(request, template, context, contacts=()):
    """
    Affiche (GET) ou met à jour (POST) la boîte mail de l'utilisateur connecté.

    ``context`` : cadre de la page (menu, titre…) ; ``contacts`` : suggestions de destinataires
    [{'name', 'email'}].
    """
    user = request.user
    if request.method == 'POST':
        query = _handle_post(request)
        return redirect(f'{request.path}?{query}' if query else request.path)

    # La corbeille se vide d'elle-même au bout de 30 jours, comme dans Gmail.
    Mail.objects.filter(owner=user, trashed_at__lt=timezone.now() - datetime.timedelta(days=TRASH_DAYS)).delete()

    labels = list(Label.objects.filter(owner=user))
    key = request.GET.get('f', 'inbox')
    label = None
    if key == 'label':
        label = next((item for item in labels if str(item.pk) == request.GET.get('l')), None)
        if label is None:
            key = 'inbox'
    elif key not in FOLDER_LABELS:
        key = 'inbox'

    query = request.GET.get('q', '').strip()
    mails = _folder_queryset(user, key, label).prefetch_related('labels')
    if query:
        mails = mails.filter(
            Q(subject__icontains=query) | Q(body__icontains=query) | Q(sender_name__icontains=query)
            | Q(sender_email__icontains=query) | Q(to__icontains=query)
        )

    page = Paginator(mails, PER_PAGE).get_page(request.GET.get('page'))
    for mail in page.object_list:
        mail.short_date = _short_date(mail.created_at)

    # Message ouvert (un brouillon ouvert se rouvre dans la fenêtre de rédaction).
    opened = None
    compose_id = request.GET.get('compose', '')
    if request.GET.get('m', '').isdigit():
        opened = get_object_or_404(Mail.objects.prefetch_related('labels'), owner=user, pk=request.GET['m'])
        if opened.folder == Mail.Folder.DRAFT:
            compose_id, opened = str(opened.pk), None
        elif not opened.is_read:
            opened.is_read = True
            opened.save(update_fields=['is_read'])

    # Fenêtre « Nouveau message » (vierge, brouillon repris, réponse ou transfert).
    compose = None
    if compose_id:
        compose = {
            'draft': '', 'to': request.GET.get('to', ''), 'subject': request.GET.get('subject', ''), 'body': '',
            'citizen': '',
        }
        draft = Mail.objects.filter(owner=user, folder=Mail.Folder.DRAFT, pk=compose_id).first() \
            if compose_id.isdigit() else None
        if draft:
            compose = {
                'draft': draft.pk, 'to': draft.to, 'subject': draft.subject, 'body': draft.body,
                'citizen': draft.citizen_id,
            }
        for mode in ('reply', 'forward'):
            if request.GET.get(mode, '').isdigit():
                source = Mail.objects.filter(owner=user, pk=request.GET[mode]).first()
                if source:
                    stamp = timezone.localtime(source.created_at).strftime('%d/%m/%Y %H:%M')
                    quoted = '\n'.join(f'> {line}' for line in source.body.splitlines())
                    if mode == 'reply':
                        compose['to'] = source.to if source.folder == Mail.Folder.SENT else source.sender_email
                        prefix = 'Re: '
                        compose['citizen'] = source.citizen_id
                        compose['body'] = f'\n\n{_("Le %(date)s, %(name)s a écrit :") % {"date": stamp, "name": source.sender_name}}\n{quoted}'
                    else:
                        prefix = 'Fwd: '
                        compose['body'] = (
                            f'\n\n---------- {_("Message transféré")} ---------\n'
                            f'{_("De")} : {source.sender_name} <{source.sender_email}>\n'
                            f'{_("Date")} : {stamp}\n{_("Objet")} : {source.subject}\n{_("À")} : {source.to}\n\n'
                            f'{source.body}'
                        )
                    subject = source.subject
                    compose['subject'] = subject if subject.lower().startswith(prefix.lower()) else prefix + subject

    undo = request.session.pop('mail_undo', None)

    def nav(key_, label_, icon, count=0):
        return {
            'key': key_, 'label': label_, 'icon': icon, 'count': count, 'active': key == key_,
            'url': f'?{urlencode({"f": key_})}',
        }

    counts = {
        'inbox': unread_count(user),
        'drafts': _folder_queryset(user, 'drafts').count(),
    }
    keep = {k: v for k, v in (('f', key), ('l', label.pk if label else ''), ('q', query)) if v}
    folder_title = label.name if label else FOLDER_LABELS[key]
    context = {
        **context,
        'mail_folders': [nav(k, l, i, counts.get(k, 0)) for k, l, i in FOLDERS],
        'mail_more': [nav(k, l, i) for k, l, i in MORE_FOLDERS],
        'mail_more_open': key in {k for k, _l, _i in MORE_FOLDERS},
        'mail_labels': [
            {'obj': item, 'active': label is not None and label.pk == item.pk,
             'url': f'?{urlencode({"f": "label", "l": item.pk})}'}
            for item in labels
        ],
        'mail_key': key,
        'mail_label': label,
        'mail_title': folder_title,
        'mail_query': query,
        'mail_page': page,
        'mail_keep': urlencode(keep),
        'mail_back': urlencode({**keep, **({'page': page.number} if page.number > 1 else {})}),
        'mail_opened': opened,
        'mail_compose': compose,
        'mail_contacts': [c for c in contacts if c.get('email')],
        'mail_undo': undo,
        'mail_snooze_choices': [
            ('later', _("Plus tard dans la journée")), ('tomorrow', _('Demain')),
            ('weekend', _('Ce week-end')), ('nextweek', _('La semaine prochaine')),
        ],
        'mail_smtp': bool(settings.EMAIL_HOST),
    }
    return render(request, template, context)
