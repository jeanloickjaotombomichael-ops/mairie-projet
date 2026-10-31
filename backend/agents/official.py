"""
Documents officiels des guichets : un document par guichet, selon son rôle.

| Guichet | Document                                   | Numéro         |
|---------|--------------------------------------------|----------------|
| 1       | Extrait d'acte de naissance                | 2026-NAI-00001 |
| 2       | Extrait d'acte de mariage                  | 2026-MAR-00001 |
| 3       | Extrait d'acte de décès                    | 2026-DEC-00001 |
| 4       | Extrait certifié conforme d'un texte       | 2026-LEG-00001 |
| 5       | Attestation de service (recette, transport…) | 2026-ATT-00001 |
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext_lazy as _

from .forms import (
    BirthCertificateForm,
    DeathCertificateForm,
    LegislationExtractForm,
    MarriageCertificateForm,
    ServiceCertificateForm,
)
from .guichets import GUICHETS
from .labels import OPTION_LABELS
from .models import (
    BirthCertificate,
    DeathCertificate,
    LegislationExtract,
    MarriageCertificate,
    ServiceCertificate,
)


def _identity_name(dossier):
    identity = dossier.identity or {}
    return f"{identity.get('last_name', '')} {identity.get('first_name', '')}".strip()


def _option(value):
    return OPTION_LABELS.get(value, value or '')


def _datetime(date_text, time_text=''):
    """« 2026-05-15 » (+ « 14:30 ») → valeur initiale d'un champ datetime-local (heure à compléter si absente)."""
    return f"{date_text}T{time_text or '00:00'}" if date_text else ''


def _copy(details, names):
    """Champs de la demande qui portent le même nom que dans le document."""
    return {name: details.get(name, '') for name in names}


def _yes(value):
    return value == 'oui'


# -- Pré-remplissage à partir de la demande de l'usager ----------------------
# Les demandes d'actes reprennent les champs du document : tout ce que le demandeur a saisi
# arrive déjà rempli dans le formulaire de l'agent. Les anciens noms (demandes déposées avant
# l'ajout de ces champs) restent lus en repli.

PARENT_FIELDS = ('full_name', 'birth_date', 'birth_place', 'profession', 'address')
SPOUSE_FIELDS = (
    'last_name', 'first_names', 'birth_date', 'birth_place', 'profession', 'address',
    'father_name', 'father_profession', 'mother_name', 'mother_profession',
)


def _prefill_birth(dossier):
    d = dossier.details or {}
    initial = {
        'child_last_name': d.get('concerned_last_name', ''),
        'child_first_names': d.get('concerned_first_name', ''),
        'child_sex': d.get('child_sex', ''),
        'birth_datetime': _datetime(d.get('birth_date'), d.get('birth_time')),
        'birth_place': d.get('birth_place', ''),
        **_copy(d, [f'{parent}_{field}' for parent in ('father', 'mother') for field in PARENT_FIELDS]),
        'declarant_name': _identity_name(dossier),
        'declarant_relationship': d.get('declarant_relationship', ''),
    }
    initial['father_full_name'] = initial['father_full_name'] or d.get('father_name', '')
    initial['mother_full_name'] = initial['mother_full_name'] or d.get('mother_name', '')
    return initial


def _prefill_marriage(dossier):
    d = dossier.details or {}
    initial = {
        'marriage_datetime': _datetime(d.get('marriage_date'), d.get('marriage_time')),
        **_copy(d, ('marriage_place', 'matrimonial_regime', 'witness1_name', 'witness1_details',
                    'witness2_name', 'witness2_details')),
        **_copy(d, [f'{spouse}_{field}' for spouse in ('husband', 'wife') for field in SPOUSE_FIELDS]),
    }
    initial['husband_last_name'] = initial['husband_last_name'] or d.get('spouse1_name', '')
    initial['wife_last_name'] = initial['wife_last_name'] or d.get('spouse2_name', '')
    return initial


def _prefill_death(dossier):
    d = dossier.details or {}
    initial = {
        **_copy(d, ('deceased_last_name', 'deceased_first_names', 'deceased_sex', 'deceased_birth_date',
                    'deceased_birth_place', 'deceased_profession', 'deceased_address', 'marital_status',
                    'spouse_name', 'father_name', 'mother_name', 'death_place', 'declarant_age',
                    'declarant_profession')),
        'father_deceased': _yes(d.get('father_deceased')),
        'mother_deceased': _yes(d.get('mother_deceased')),
        'death_datetime': _datetime(d.get('death_date'), d.get('death_time')),
        'declarant_name': _identity_name(dossier),
        'declarant_relationship': _option(d.get('relationship')).lower(),
        'declarant_address': (dossier.identity or {}).get('address', ''),
    }
    initial['deceased_last_name'] = initial['deceased_last_name'] or d.get('deceased_name', '')
    return initial


def _prefill_legislation(dossier):
    d = dossier.details or {}
    return {
        'text_type': d.get('text_type', ''),
        'text_number': d.get('reference_number', ''),
        'text_date': d.get('text_date', ''),
        'subject': d.get('subject', ''),
        'recipient_name': _identity_name(dossier),
    }


# Guichet 5 : champ de la demande → référence / lieu, selon le service.
SERVICE_REFERENCE = {
    'recette': 'reference_number', 'transport': 'vehicle_plate', 'cadastre': 'parcel_reference',
    'marche': 'stall_number', 'impot_foncier': 'tax_reference', 'urbanisme': 'cadastral_reference',
}
SERVICE_LOCATION = {
    'urbanisme': 'plot_address', 'marche': 'market_name', 'impot_foncier': 'property_address',
    'cadastre': 'district',
}
SERVICE_NATURE = {'recette': 'payment_type', 'actes_divers': 'act_nature'}


def _prefill_service(dossier):
    d = dossier.details or {}
    identity = dossier.identity or {}
    service = dossier.dossier_type
    nature_value = d.get(SERVICE_NATURE.get(service, 'request_kind'), '')
    subject_parts = [d.get(key, '') for key in ('works_description', 'activity', 'description', 'period')]
    if service == 'transport' and d.get('vehicle_type'):
        subject_parts.insert(0, f"Véhicule : {_option(d['vehicle_type'])}")
    if service == 'impot_foncier' and d.get('tax_year'):
        subject_parts.insert(0, f"Année d'imposition {d['tax_year']}")
    initial = {
        'service': service,
        'nature': _option(nature_value),
        'holder_full_name': _identity_name(dossier),
        'holder_national_id': identity.get('national_id', ''),
        'holder_address': identity.get('address', ''),
        'reference': d.get(SERVICE_REFERENCE.get(service, ''), ''),
        'location': d.get(SERVICE_LOCATION.get(service, ''), ''),
        'subject': ' — '.join(part for part in subject_parts if part),
    }
    if service == 'recette' and d.get('amount'):
        try:
            initial['amount'] = Decimal(str(d['amount']).replace(',', '.'))
        except InvalidOperation:
            pass
    return initial


# -- Registre ------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentSpec:
    guichet: int
    model: type
    form: type
    prefill: object
    new_label: str        # « Nouvel acte de naissance »
    issue_label: str      # bouton sur la fiche d'une demande
    holder_header: str    # colonne « titulaire » de la liste
    date_header: str      # colonne « date » de la liste

    @property
    def request_types(self):
        """Types de demande auxquels ce document répond (ceux du guichet)."""
        return GUICHETS[self.guichet].dossier_types

    @property
    def plural(self):
        return self.model._meta.verbose_name_plural


OFFICIAL_DOCUMENTS = {
    1: DocumentSpec(1, BirthCertificate, BirthCertificateForm, _prefill_birth,
                    _('Nouvel acte de naissance'), _("Établir l'acte de naissance"), _('Enfant'), _('Né(e) le')),
    2: DocumentSpec(2, MarriageCertificate, MarriageCertificateForm, _prefill_marriage,
                    _('Nouvel acte de mariage'), _("Établir l'acte de mariage"), _('Époux'), _('Marié(s) le')),
    3: DocumentSpec(3, DeathCertificate, DeathCertificateForm, _prefill_death,
                    _('Nouvel acte de décès'), _("Établir l'acte de décès"), _('Défunt'), _('Décédé(e) le')),
    4: DocumentSpec(4, LegislationExtract, LegislationExtractForm, _prefill_legislation,
                    _('Nouvel extrait de texte'), _("Établir l'extrait certifié"), _('Texte'), _('Date du texte')),
    5: DocumentSpec(5, ServiceCertificate, ServiceCertificateForm, _prefill_service,
                    _('Nouvelle attestation'), _("Établir l'attestation"), _('Bénéficiaire'), _("Date de l'acte")),
}

DOCUMENT_MODELS = tuple(spec.model for spec in OFFICIAL_DOCUMENTS.values())


def find_document(pk):
    """Document officiel (tous guichets) par identifiant, ou None."""
    for model in DOCUMENT_MODELS:
        document = model.objects.filter(pk=pk).first()
        if document is not None:
            return document
    return None


def documents_for_request(dossier, **filters):
    """Documents établis pour une demande d'usager (tous types)."""
    found = []
    for model in DOCUMENT_MODELS:
        found.extend(model.objects.filter(request=dossier, **filters))
    return found


def documents_for_requests(dossier_ids):
    """{id de demande: [documents]} pour une liste de demandes (une requête par type de document)."""
    ids = list(dossier_ids)  # peut être un générateur : on ne le parcourt qu'une fois
    grouped = {}
    for model in DOCUMENT_MODELS:
        for document in model.objects.filter(request_id__in=ids):
            grouped.setdefault(document.request_id, []).append(document)
    return grouped
