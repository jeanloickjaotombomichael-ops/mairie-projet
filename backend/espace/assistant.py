"""
Assistant IA (local, sans service externe) de l'espace usager.

Il comprend des phrases simples par mots-clés et ne travaille que sur les données de l'usager
connecté : ses demandes, les réponses de la mairie, ses documents et ses messages. Il oriente
aussi vers la bonne démarche. Les liens renvoyés (« items ») sont des chemins du frontend.
"""
import re
import unicodedata

from django.utils.formats import date_format
from django.utils.translation import gettext as _

from .models import DossierRequest

Status = DossierRequest.Status
T = DossierRequest.DossierType

HELP_WORDS = ('aide', 'help', 'que peux', 'que sais', 'bonjour', 'salut', 'bonsoir', 'hello', 'manao ahoana', 'fanampiana')
STATUS_WORDS = ('mes demandes', 'ma demande', 'statut', 'ou en est', 'suivi', 'avancement', 'etat de', 'dossier')
RESPONSE_WORDS = ('reponse', 'repondu', 'notification', 'non lu', 'valide', 'refus', 'approuv')
DOCUMENT_WORDS = ('document', 'telecharg', 'pdf', 'copie', 'pret', 'disponible', 'recuper')
MAIL_WORDS = ('mail', 'message', 'ecrire', 'contacter un agent', 'joindre', 'question a', 'guichet')
CONTACT_WORDS = ('contact', 'adresse', 'telephone', 'horaire', 'ouvert', 'ou se trouve', 'hotel de ville')
VERIFY_WORDS = ('verifier', 'authentique', 'qr', 'faux', 'scanner')
THANKS_WORDS = ('merci', 'thanks', 'misaotra')
REFERENCE_RE = re.compile(r'\bmv[\s-]?(\d{4})[\s-]?(\d{1,6})\b', re.IGNORECASE)

# Démarches : (type, mots-clés, chemin du formulaire dans l'espace).
PROCEDURES = (
    (T.NAISSANCE, ('naissance', 'ne le', 'bebe', 'enfant'), '/espace/demande/naissance'),
    (T.MARIAGE, ('mariage', 'marier', 'epoux', 'epouse'), '/espace/demande/mariage'),
    (T.DECES, ('deces', 'decede', 'defunt', 'mort'), '/espace/demande/deces'),
    (T.LEGISLATION, ('legislation', 'arrete', 'deliberation', 'loi', 'reglement'), '/espace/demande/legislation'),
    (T.ACTES_DIVERS, ('actes divers', 'autre acte', 'certificat de residence', 'attestation'), '/espace/demande/actes-divers'),
    (T.RECETTE, ('recette', 'taxe', 'patente', 'payer', 'paiement', 'redevance'), '/espace/demande/recette'),
    (T.TRANSPORT, ('transport', 'taxi', 'bus', 'bajaj', 'licence', 'stationnement', 'vehicule'), '/espace/demande/transport'),
    (T.URBANISME, ('urbanisme', 'permis', 'construire', 'construction', 'travaux', 'alignement'), '/espace/demande/urbanisme'),
    (T.MARCHE, ('marche', 'emplacement', 'etal', 'stand'), '/espace/demande/marche'),
    (T.CADASTRE, ('cadastre', 'parcelle', 'bornage', 'terrain'), '/espace/demande/cadastre'),
    (T.IMPOT_FONCIER, ('impot', 'foncier', 'avis d imposition'), '/espace/demande/impot-foncier'),
)


def _normalize(text):
    text = unicodedata.normalize('NFKD', text.lower())
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return ' '.join(text.replace("'", ' ').replace('’', ' ').split())


def _has(text, words):
    return any(word in text for word in words)


def _dossier_item(dossier):
    return {
        'label': f'{dossier.reference} — {dossier.get_dossier_type_display()}',
        'meta': f'{dossier.get_status_display()} · {date_format(dossier.created_at, "d/m/Y")}',
        'url': '/espace/notifications',
    }


def _reply(text, items=()):
    return {'text': text, 'items': list(items)}


def _help():
    return _reply(_(
        "Je suis l'assistant de votre espace. Je peux : vous dire où en sont vos demandes (ou une demande "
        "précise, ex. « MV-2026-000005 »), vous signaler les réponses de la mairie et les documents à "
        "télécharger, vous orienter vers la bonne démarche (ex. « acte de naissance », « permis de "
        "construire ») et vous aider à écrire à un guichet."
    ), [
        {'label': _('Mes demandes'), 'meta': _('Suivi et réponses'), 'url': '/espace/notifications'},
        {'label': _('Écrire à la mairie'), 'meta': _('Mail'), 'url': '/espace/mail'},
    ])


def answer(clerk_user_id, message):
    text = _normalize(message)
    dossiers = DossierRequest.objects.filter(clerk_user_id=clerk_user_id)

    # Une demande précise, par sa référence.
    match = REFERENCE_RE.search(message)
    if match:
        reference = f'MV-{match.group(1)}-{int(match.group(2)):06d}'
        dossier = dossiers.filter(reference=reference).first()
        if dossier is None:
            return _reply(_("Je ne trouve pas la demande %(ref)s parmi les vôtres. Vérifiez la référence.")
                          % {'ref': reference})
        parts = [_('Votre demande %(ref)s (%(type)s) est « %(status)s ».') % {
            'ref': dossier.reference, 'type': dossier.get_dossier_type_display(),
            'status': dossier.get_status_display(),
        }]
        if dossier.response_message.strip():
            parts.append(_('Réponse de la mairie : « %(text)s »') % {'text': dossier.response_message.strip()})
        elif dossier.status in (Status.PENDING, Status.IN_PROGRESS):
            parts.append(_("La mairie ne vous a pas encore répondu : vous serez prévenu dans vos notifications."))
        return _reply(' '.join(parts), [_dossier_item(dossier)])

    if _has(text, THANKS_WORDS):
        return _reply(_('Avec plaisir ! Autre chose ?'))

    if _has(text, HELP_WORDS) and len(text) < 40:
        return _help()

    if _has(text, DOCUMENT_WORDS):
        from agents.official import documents_for_requests

        own = list(dossiers)
        documents = documents_for_requests(dossier.pk for dossier in own)
        ready = [
            (dossier, act) for dossier in own for act in documents.get(dossier.pk, []) if act.downloadable_by_requester
        ]
        if not ready:
            return _reply(_(
                "Aucun document n'est encore disponible. Quand un agent vous envoie un document (ex. une copie "
                "d'acte), il apparaît dans vos notifications, prêt à télécharger."
            ))
        return _reply(_('%(count)s document(s) à télécharger dans vos notifications :') % {'count': len(ready)}, [
            {'label': act.label, 'meta': dossier.reference, 'url': '/espace/notifications'} for dossier, act in ready[:6]
        ])

    if _has(text, RESPONSE_WORDS):
        answered = dossiers.exclude(response_message='')
        unread = answered.filter(response_read=False)
        if not answered.exists():
            return _reply(_("La mairie n'a encore répondu à aucune de vos demandes."))
        if unread.exists():
            return _reply(_('Vous avez %(count)s réponse(s) non lue(s) :') % {'count': unread.count()},
                          [_dossier_item(dossier) for dossier in unread[:5]])
        return _reply(_('Vous avez lu toutes les réponses de la mairie (%(count)s).') % {'count': answered.count()},
                      [_dossier_item(dossier) for dossier in answered[:3]])

    if _has(text, VERIFY_WORDS):
        return _reply(_("Pour vérifier qu'un document de la mairie est authentique, scannez son QR code."), [
            {'label': _('Vérifier un document'), 'meta': _('Scanner le QR code'), 'url': '/scanner'},
        ])

    if _has(text, CONTACT_WORDS):
        return _reply(_("Vous trouverez l'adresse, le téléphone et les horaires de la mairie sur la page Contact. "
                        "Vous pouvez aussi écrire directement à un guichet depuis « Mail »."), [
            {'label': _('Contact'), 'meta': _('Coordonnées de la mairie'), 'url': '/contact'},
            {'label': _('Écrire à un guichet'), 'meta': _('Mail'), 'url': '/espace/mail'},
        ])

    # Démarche demandée.
    found = [(kind, path) for kind, words, path in PROCEDURES if _has(text, words)]
    if found:
        return _reply(_("Voici la démarche qui correspond. Remplissez le formulaire : la demande arrive directement "
                        "au guichet concerné."), [
            {'label': kind.label, 'meta': _('Faire la demande'), 'url': path} for kind, path in found[:3]
        ])

    if _has(text, MAIL_WORDS):
        return _reply(_("Depuis « Mail », choisissez le guichet (ou l'administration), écrivez votre message : "
                        "la réponse de l'agent arrivera dans votre boîte."), [
            {'label': _('Nouveau message'), 'meta': _('Mail'), 'url': '/espace/mail?nouveau=1'},
        ])

    if _has(text, STATUS_WORDS) or 'demande' in text:
        latest = list(dossiers[:5])
        if not latest:
            return _reply(_("Vous n'avez encore envoyé aucune demande. Dites-moi ce dont vous avez besoin "
                            "(ex. « acte de naissance ») et je vous indique le formulaire."))
        open_count = dossiers.filter(status__in=[Status.PENDING, Status.IN_PROGRESS]).count()
        return _reply(_('Vous avez %(total)s demande(s), dont %(open)s en attente ou en cours. Les plus récentes :') % {
            'total': dossiers.count(), 'open': open_count,
        }, [_dossier_item(dossier) for dossier in latest])

    if _has(text, HELP_WORDS):
        return _help()

    reply = _help()
    reply['text'] = _("Je n'ai pas bien compris. ") + reply['text']
    return reply
