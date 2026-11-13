"""Schéma des champs des demandes (identité + détails propres à chaque dossier).

Ce module est la référence côté serveur : le frontend (formulaires dynamiques)
utilise les mêmes noms de champs. Toutes les valeurs arrivent sous forme de
chaînes ; les clés inconnues sont ignorées et les valeurs vides des champs
facultatifs ne sont pas conservées.
"""
import datetime
import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

# Codes d'erreur renvoyés au frontend.
REQUIRED = 'required'
INVALID = 'invalid'
TOO_LONG = 'too_long'

# Types de champ.
TEXT = 'text'
TEXTAREA = 'textarea'
DATE = 'date'
INTEGER = 'integer'
NUMBER = 'number'
SELECT = 'select'
EMAIL = 'email'
PHONE = 'phone'
CIN = 'cin'
TIME = 'time'

PHONE_PATTERN = re.compile(r'^[0-9+()\-.\s]{6,30}$')
# N° de CIN malgache : 12 chiffres, espaces de groupement acceptés (« 101 234 567 890 »).
CIN_PATTERN = re.compile(r'^\d{12}$')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
TIME_PATTERN = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
INTEGER_PATTERN = re.compile(r'^\d{1,4}$')
NUMBER_PATTERN = re.compile(r'^\d+([.,]\d+)?$')

TEXT_MAX = 200
TEXTAREA_MAX = 2000


@dataclass(frozen=True)
class FieldSpec:
    """Description d'un champ de formulaire."""

    name: str
    kind: str = TEXT
    required: bool = False
    choices: tuple = ()
    max_length: int = TEXT_MAX
    minimum: int | None = None
    maximum: int | None = None


def _text(name, required=False, max_length=TEXT_MAX):
    return FieldSpec(name, TEXT, required, max_length=max_length)


def _textarea(name, required=False):
    return FieldSpec(name, TEXTAREA, required, max_length=TEXTAREA_MAX)


def _date(name, required=True):
    return FieldSpec(name, DATE, required, max_length=10)


def _time(name):
    """Heure facultative (« 14:30 ») : complète une date (naissance, mariage, décès)."""
    return FieldSpec(name, TIME, False, max_length=5)


def _integer(name, minimum, maximum, required=True):
    return FieldSpec(name, INTEGER, required, max_length=4, minimum=minimum, maximum=maximum)


def _copies():
    return _integer('copies', 1, 10)


def _select(name, choices, required=True):
    return FieldSpec(name, SELECT, required, choices=tuple(choices))


def _number(name):
    return FieldSpec(name, NUMBER, False, max_length=20)


# ----------------------------------------------------------------------
# Identité du demandeur (commune à tous les dossiers)
# ----------------------------------------------------------------------
IDENTITY_FIELDS = (
    _text('last_name', True, 100),
    _text('first_name', True, 100),
    # E-mail et téléphone facultatifs : beaucoup d'usagers (notamment en zone rurale) n'en ont pas.
    FieldSpec('email', EMAIL, False, max_length=254),
    FieldSpec('phone', PHONE, False, max_length=30),
    FieldSpec('national_id', CIN, False, max_length=30),
    _text('address', False, 200),
)

# Champ accepté pour tous les types de dossier.
COMMON_DETAIL_FIELDS = (_textarea('comment'),)

# Fokontany de la Commune urbaine de Mahajanga (liste à tenir à jour avec la Commune) ;
# repris tel quel dans frontend/src/data/formSchema.ts.
FOKONTANY = (
    'Abattoir', 'Ambalavola', 'Ambohimandamina', 'Ambondrona', 'Amborovy', 'Ambovoalanana', 'Ampisikina',
    'Antanimalandy', 'Antanimasaja', 'Antsahabingo', 'Aranta', 'Fiofio', 'Mahabibo', 'Mahajanga Be',
    'Mahatsinjo', 'Mahavoky Atsimo', 'Mahavoky Avaratra', 'Manga', 'Mangarivotra', 'Manjarisoa', 'Morafeno',
    'Tanambao Sotema', 'Tsaramandroso Ambany', 'Tsaramandroso Ambony', 'Tsararano Ambany', 'Tsararano Ambony',
)

# Étape « Quartier » des demandes d'actes (naissance, mariage, décès, législation).
QUARTIER_FIELDS = (
    FieldSpec('fokontany', SELECT, True, choices=FOKONTANY, max_length=60),
    _select('main_residence', ('oui', 'non')),
)

SEXES = ('M', 'F')


def _person(prefix, required):
    """Parent de l'enfant (acte de naissance) : nom complet, naissance, profession, domicile."""
    return (
        _text(f'{prefix}_full_name', required),
        _date(f'{prefix}_birth_date', required),
        _text(f'{prefix}_birth_place', required),
        _text(f'{prefix}_profession', False, 150),
        _text(f'{prefix}_address', required, 255),
    )


def _spouse(prefix):
    """Époux ou épouse (acte de mariage), avec ses parents."""
    return (
        _text(f'{prefix}_last_name', True, 150),
        _text(f'{prefix}_first_names', True),
        _date(f'{prefix}_birth_date'),
        _text(f'{prefix}_birth_place', True),
        _text(f'{prefix}_profession', False, 150),
        _text(f'{prefix}_address', True, 255),
        _text(f'{prefix}_father_name'),
        _text(f'{prefix}_father_profession', False, 150),
        _text(f'{prefix}_mother_name'),
        _text(f'{prefix}_mother_profession', False, 150),
    )


# ----------------------------------------------------------------------
# Détails propres à chaque type de dossier
# ----------------------------------------------------------------------
DETAIL_FIELDS = {
    # Actes : les mêmes informations que le document officiel (agents/forms.py), saisies par le
    # demandeur puis reprises automatiquement dans le formulaire de l'agent (agents/official.py).
    'naissance': (
        _text('concerned_last_name', True),
        _text('concerned_first_name', True),
        _select('child_sex', SEXES),
        _date('birth_date'),
        _time('birth_time'),
        _text('birth_place', True),
        *_person('father', required=False),
        *_person('mother', required=True),
        _text('declarant_relationship', False, 150),
        _copies(),
        *QUARTIER_FIELDS,
    ),
    'mariage': (
        _date('marriage_date'),
        _time('marriage_time'),
        _text('marriage_place', True),
        _text('matrimonial_regime', False, 500),
        *_spouse('husband'),
        *_spouse('wife'),
        _text('witness1_name', True),
        _text('witness1_details', False, 255),
        _text('witness2_name', True),
        _text('witness2_details', False, 255),
        _copies(),
        *QUARTIER_FIELDS,
    ),
    'deces': (
        _text('deceased_last_name', True, 150),
        _text('deceased_first_names', True),
        _select('deceased_sex', SEXES),
        _date('deceased_birth_date', False),
        _text('deceased_birth_place'),
        _text('deceased_profession', False, 150),
        _text('deceased_address', True, 255),
        _select('marital_status', ('SINGLE', 'MARRIED', 'WIDOWED', 'DIVORCED'), required=False),
        _text('spouse_name'),
        _text('father_name'),
        _select('father_deceased', ('oui', 'non'), required=False),
        _text('mother_name'),
        _select('mother_deceased', ('oui', 'non'), required=False),
        _date('death_date'),
        _time('death_time'),
        _text('death_place', True),
        _select('relationship', ('spouse', 'child', 'parent', 'sibling', 'other')),
        _integer('declarant_age', 10, 120, required=False),
        _text('declarant_profession', False, 150),
        _copies(),
        *QUARTIER_FIELDS,
    ),
    'legislation': (
        _select('text_type', ('arrete', 'deliberation', 'reglement', 'decision', 'other')),
        _text('reference_number'),
        _date('text_date', False),
        _text('subject', True),
        *QUARTIER_FIELDS,
    ),
    'actes_divers': (
        _text('act_nature', True),
        _textarea('description', True),
        _copies(),
    ),
    'recette': (
        _select('payment_type', ('taxe_marche', 'patente', 'droit_place', 'location', 'other')),
        _text('reference_number'),
        _number('amount'),
        _text('period'),
    ),
    'urbanisme': (
        _select(
            'request_kind',
            ('permis_construire', 'certificat_urbanisme', 'autorisation_travaux', 'alignement'),
        ),
        _text('plot_address', True),
        _textarea('works_description', True),
        _number('surface'),
        _text('cadastral_reference'),
    ),
    'transport': (
        _select(
            'request_kind',
            ('licence', 'carte_stationnement', 'autorisation_ligne', 'renouvellement'),
        ),
        _select('vehicle_type', ('taxi', 'bus', 'pousse_pousse', 'bajaj', 'moto', 'other')),
        _text('vehicle_plate', True),
        _text('license_number'),
    ),
    'marche': (
        _select('request_kind', ('emplacement', 'renouvellement', 'transfert', 'resiliation')),
        _text('market_name', True),
        _text('activity', True),
        _text('stall_number'),
    ),
    'cadastre': (
        _select('request_kind', ('extrait', 'certificat_propriete', 'bornage', 'mutation')),
        _text('parcel_reference', True),
        _text('district', True),
        _text('title_number'),
    ),
    'impot_foncier': (
        _select(
            'request_kind',
            ('declaration', 'avis_imposition', 'attestation_paiement', 'reclamation'),
        ),
        _text('property_address', True),
        _integer('tax_year', 2000, 2100),
        _text('tax_reference'),
    ),
}


def detail_specs(dossier_type):
    """Champs de détails d'un type de dossier (None si le type est inconnu)."""
    specs = DETAIL_FIELDS.get(dossier_type)
    if specs is None:
        return None
    return specs + COMMON_DETAIL_FIELDS


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def clean_value(spec, raw):
    """Valide une valeur. Retourne ``(valeur_nettoyée, code_erreur)``.

    Une valeur vide d'un champ facultatif donne ``('', None)``.
    """
    if raw is None:
        value = ''
    elif isinstance(raw, bool):
        return None, INVALID
    elif isinstance(raw, (int, float)):
        value = str(raw)
    elif isinstance(raw, str):
        value = raw.strip()
    else:
        return None, INVALID

    if not value:
        if spec.required:
            return None, REQUIRED
        return '', None

    if len(value) > spec.max_length:
        return None, TOO_LONG

    if spec.kind == EMAIL:
        try:
            validate_email(value)
        except ValidationError:
            return None, INVALID
    elif spec.kind == PHONE:
        if not PHONE_PATTERN.match(value):
            return None, INVALID
    elif spec.kind == CIN:
        if not CIN_PATTERN.match(re.sub(r'\s', '', value)):
            return None, INVALID
    elif spec.kind == DATE:
        if not DATE_PATTERN.match(value):
            return None, INVALID
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            return None, INVALID
    elif spec.kind == TIME:
        if not TIME_PATTERN.match(value):
            return None, INVALID
    elif spec.kind == INTEGER:
        if not INTEGER_PATTERN.match(value):
            return None, INVALID
        number = int(value)
        if spec.minimum is not None and number < spec.minimum:
            return None, INVALID
        if spec.maximum is not None and number > spec.maximum:
            return None, INVALID
    elif spec.kind == NUMBER:
        if not NUMBER_PATTERN.match(value):
            return None, INVALID
    elif spec.kind == SELECT:
        if value not in spec.choices:
            return None, INVALID

    return value, None


def clean_fields(specs, data, prefix=''):
    """Valide ``data`` (dict) selon ``specs``.

    Retourne ``(valeurs, erreurs)`` : ``valeurs`` ne contient que les champs
    connus et non vides ; ``erreurs`` associe ``[prefix.]nom`` à ``[code]``.
    """
    source = data if isinstance(data, dict) else {}
    cleaned = {}
    errors = {}
    for spec in specs:
        value, error = clean_value(spec, source.get(spec.name))
        key = f'{prefix}.{spec.name}' if prefix else spec.name
        if error:
            errors[key] = [error]
        elif value:
            cleaned[spec.name] = value
    return cleaned, errors


# Champs du formulaire de contact (public).
CONTACT_FIELDS = (
    _text('first_name', True, 100),
    _text('last_name', False, 100),
    FieldSpec('phone', PHONE, True, max_length=30),
    FieldSpec('email', EMAIL, True, max_length=254),
    _textarea('message'),
)
