"""Guichets de la Commune : chaque agent est rattaché à un seul guichet et ne traite que ses demandes."""
from dataclasses import dataclass

from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from espace.models import DossierRequest

T = DossierRequest.DossierType


@dataclass(frozen=True)
class Guichet:
    number: int
    label: str
    dossier_types: tuple

    @property
    def title(self):
        return format_lazy(_('Guichet {number}'), number=self.number)


GUICHETS = {
    1: Guichet(1, _('Actes de naissance'), (T.NAISSANCE,)),
    2: Guichet(2, _('Actes de mariage'), (T.MARIAGE,)),
    3: Guichet(3, _('Actes de décès'), (T.DECES,)),
    4: Guichet(4, _('Législation'), (T.LEGISLATION,)),
    5: Guichet(5, _('Recette, transport, marché et autres services'), (
        T.RECETTE, T.TRANSPORT, T.URBANISME, T.MARCHE, T.CADASTRE, T.IMPOT_FONCIER, T.ACTES_DIVERS,
    )),
}

GUICHET_CHOICES = [(number, format_lazy('{} — {}', g.title, g.label)) for number, g in GUICHETS.items()]

# Type de dossier → numéro du guichet qui le traite.
GUICHET_BY_TYPE = {dossier_type: number for number, g in GUICHETS.items() for dossier_type in g.dossier_types}


def guichet_for_type(dossier_type):
    """Numéro du guichet chargé d'un type de demande (None si inconnu)."""
    return GUICHET_BY_TYPE.get(dossier_type)
