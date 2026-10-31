"""
File d'attente des demandes : premier arrivé, premier servi.

Pour chaque type de demande (ex. acte de mariage), les demandes « en attente » se traitent
dans leur ordre d'arrivée : un agent ne peut traiter une demande en attente que si aucune
demande plus ancienne du même type n'attend encore. Dès que la plus ancienne est prise en
charge (son statut change), la suivante devient traitable. Les demandes déjà prises en
charge ne bloquent rien. Chaque type a sa propre file : au guichet 5, une demande de
transport n'attend pas une demande de recette.
"""
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from espace.models import DossierRequest

PENDING = DossierRequest.Status.PENDING


def blocking_request(dossier):
    """Demande plus ancienne du même type, encore en attente, à traiter avant `dossier` (sinon None)."""
    if dossier is None or dossier.status != PENDING:
        return None
    return (
        DossierRequest.objects.filter(dossier_type=dossier.dossier_type, status=PENDING)
        .filter(Q(created_at__lt=dossier.created_at) | Q(created_at=dossier.created_at, pk__lt=dossier.pk))
        .order_by('created_at', 'pk')
        .first()
    )


def blocked_message(blocker):
    return _(
        'Attention : vous devez d\'abord traiter la demande %(reference)s, déposée le %(date)s, '
        'avant celle-ci. Les demandes se traitent dans leur ordre d\'arrivée.'
    ) % {
        'reference': blocker.reference,
        'date': date_format(timezone.localtime(blocker.created_at), 'DATETIME_FORMAT'),
    }


def annotate_positions(dossiers, dossier_types):
    """Ajoute `queue_position` (1 = à traiter en premier) aux demandes en attente de la liste."""
    order = (
        DossierRequest.objects.filter(dossier_type__in=dossier_types, status=PENDING)
        .order_by('created_at', 'pk')
        .values_list('pk', 'dossier_type')
    )
    positions, counters = {}, {}
    for pk, dossier_type in order:
        counters[dossier_type] = counters.get(dossier_type, 0) + 1
        positions[pk] = counters[dossier_type]
    for dossier in dossiers:
        dossier.queue_position = positions.get(dossier.pk)
    return dossiers
