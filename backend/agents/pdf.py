"""PDF des guichets.

- ticket_pdf(act)   : bon de retrait remis au citoyen (petit ticket avec QR code, sans le contenu de l'acte).
- document_pdf(act) : document officiel imprimé au guichet, signé et cacheté (sans QR code ni empreinte).
"""
import io
from pathlib import Path

import qrcode
from django.conf import settings
from django.utils import timezone, translation
from django.utils.html import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import lettres, lettres_mg

NAVY = colors.HexColor('#1f3a63')
BLUE = colors.HexColor('#2f6db5')
GREY = colors.HexColor('#5b6475')
LIGHT = colors.HexColor('#eaf0f6')
LINE = colors.HexColor('#d5dde8')

LOGO = Path(settings.BASE_DIR) / 'static' / 'mairy_admin' / 'logo.png'

STYLES = {
    'country': ParagraphStyle('country', fontName='Helvetica-Bold', fontSize=17, leading=21,
                              textColor=NAVY, alignment=TA_CENTER),
    'motto': ParagraphStyle('motto', fontName='Helvetica-Oblique', fontSize=9.5, leading=12,
                            textColor=GREY, alignment=TA_CENTER),
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=18.5, leading=23,
                            textColor=NAVY, alignment=TA_CENTER, spaceBefore=8),
    'subtitle': ParagraphStyle('subtitle', fontName='Helvetica-BoldOblique', fontSize=10.5, leading=14,
                               textColor=GREY, alignment=TA_CENTER),
    'cell': ParagraphStyle('cell', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=colors.HexColor('#333a46')),
    'heading': ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=12.5, leading=16,
                              textColor=BLUE, spaceBefore=9, spaceAfter=4),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10.5, leading=15.5, alignment=TA_JUSTIFY),
    'notes': ParagraphStyle('notes', fontName='Helvetica-Oblique', fontSize=10, leading=14),
    'sign': ParagraphStyle('sign', fontName='Helvetica-Bold', fontSize=10.5, leading=14),
    'sign_note': ParagraphStyle('sign_note', fontName='Helvetica-Oblique', fontSize=9.5, leading=13, textColor=GREY),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=10.5, textColor=GREY),
    'cell_plain': ParagraphStyle('cell_plain', fontName='Helvetica', fontSize=9.5, leading=12.5,
                                 textColor=colors.HexColor('#333a46')),
    'body_left': ParagraphStyle('body_left', fontName='Helvetica', fontSize=10.5, leading=15.5),
    'country_left': ParagraphStyle('country_left', fontName='Helvetica-Bold', fontSize=11.5, leading=14,
                                   textColor=GREY),
    'motto_left': ParagraphStyle('motto_left', fontName='Helvetica-Oblique', fontSize=8.5, leading=11,
                                 textColor=GREY),
    'service_left': ParagraphStyle('service_left', fontName='Helvetica', fontSize=10.5, leading=14,
                                   textColor=GREY, spaceBefore=2),
    'mono': ParagraphStyle('mono', fontName='Courier', fontSize=7.6, leading=10, textColor=colors.HexColor('#333a46')),
}


def _b(text):
    return f'<b>{escape(text)}</b>'


def _person(lang, label, name, feminine, place, birth_date, profession, address):
    """« PÈRE : <b>Nom</b>, né à X le …, profession de …, domicilié au … » (parties connues seulement)."""
    L = _lettres(lang)
    parts = [f'<b>{label} : {escape(name)}</b>']
    if place or birth_date:
        if lang == 'mg':
            born = 'teraka'
            if place:
                born += f' tao {escape(place)}'
            if birth_date:
                born += f" tamin'ny {L.date(birth_date)}"
        else:
            born = 'née' if feminine else 'né'
            if place:
                born += f' à {escape(place)}'
            if birth_date:
                born += f' le {L.date(birth_date)}'
        parts.append(born)
    if profession:
        if lang == 'mg':
            parts.append(f'asa : {escape(profession)}')
        else:
            parts.append(f"profession d'{escape(profession)}" if profession[:1].lower() in 'aeiouéèêh'
                         else f'profession de {escape(profession)}')
    if address:
        if lang == 'mg':
            parts.append(f'monina ao {escape(address)}')
        else:
            parts.append(f"{'domiciliée' if feminine else 'domicilié'} au {escape(address)}")
    return ', '.join(parts) + '.'


def _qr_image(url, size):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=1, box_size=8)
    qr.add_data(url)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(buffer, format='PNG')
    buffer.seek(0)
    return Image(buffer, width=size, height=size)


class BonDejaRetire(Exception):
    """Le document a déjà été retiré au guichet : le bon de retrait et son QR code ne servent plus."""


def is_retrieved(act):
    """Vrai quand l'agent a scanné le bon et remis le document officiel (champ retrieved_at rempli)."""
    return getattr(act, 'retrieved_at', None) is not None


def qr_png(url, act=None):
    """QR code PNG (octets) pour l'aperçu dans l'espace agent.

    Renvoie None si le document a déjà été retiré : plus aucun QR code n'est affiché après le retrait."""
    if act is not None and is_retrieved(act):
        return None
    image = qrcode.make(url, border=1)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def _amount(value):
    """125000.5 → « 125 000,50 Ar »."""
    return f'{value:,.2f}'.replace(',', ' ').replace('.', ',') + ' Ar'


def _paragraph(text):
    return Paragraph(escape(text).replace('\n', '<br/>'), STYLES['body'])


# -- Langue du document ------------------------------------------------------------
# Le document officiel est rédigé en malgache par défaut ('mg'), ou en français ('fr').
# Chaque texte figure dans les deux langues côte à côte : _t(lang, français, malgache).

LANGUAGES = ('mg', 'fr')


def _t(lang, fr, mg):
    return mg if lang == 'mg' else fr


def _lettres(lang):
    return lettres_mg if lang == 'mg' else lettres


def _std(lang, value):
    """Valeurs par défaut saisies en français (qualité de l'officier, mentions) : traduites en malgache."""
    if lang != 'mg':
        return value
    from .models import DEFAULT_MARGINAL_NOTES

    return {
        "Officier de l'état civil": 'Mpiandraikitra ny fiankohonana',
        'Sans objet.': 'Tsy misy.',
        'Néant.': 'Tsy misy.',
        DEFAULT_MARGINAL_NOTES: "Tsy misy. (Tsy nisy fanamarihana fanampiny voasoratra hatramin'ny andro "
                                'nanomezana ity dika ity).',
    }.get((value or '').strip(), value)


def _commune(act, lang):
    """« Commune Urbaine de Mahajanga » → « Kaominina Ambonivohitr'i Mahajanga » en malgache."""
    if lang != 'mg':
        return act.commune
    for prefix, mg in (('Commune Urbaine de ', "Kaominina Ambonivohitr'i "),
                       ('Commune Rurale de ', "Kaominina Ambanivohitr'i "), ('Commune de ', "Kaominin'i ")):
        if act.commune.startswith(prefix):
            return mg + act.commune[len(prefix):]
    return act.commune


MG_TITLES = {
    'BirthCertificate': "KOPIAN'NY SORA-PAHATERAHANA",
    'MarriageCertificate': "SORA-PANAMBADIANA (DIKA FENO)",
    'DeathCertificate': "DIKA FENON'NY SORA-PAHAFATESANA",
    'LegislationExtract': 'SOMBIN-TSORATRA VOAMARINA FA MITOVY AMIN\'NY TANY AM-BOALOHANY',
}
MG_SERVICE_TITLES = {
    'recette': 'FANAMARINANA FANDOAVAM-BOLA',
    'transport': 'FAHAZOAN-DÀLANA MOMBA NY FITATERANA',
    'urbanisme': 'FAHAZOAN-DÀLANA MOMBA NY FANDRAFETAN-TANÀNA',
    'marche': 'FANAMARINANA TOERANA ANY AN-TSENA',
    'cadastre': 'SOMBINY AVY AMIN\'NY KADASITRA',
    'impot_foncier': "FANAMARINANA NY HETRA AMIN'NY TANY",
    'actes_divers': 'FANAMARINANA ARA-PITANTANANA',
}


def _title(act, lang):
    if lang != 'mg':
        return act.document_title
    name = type(act).__name__
    if name == 'ServiceCertificate':
        return MG_SERVICE_TITLES.get(act.service, 'FANAMARINANA')
    return MG_TITLES.get(name, act.document_title)


# -- Mise en page propre à chaque document ----------------------------------------
# Chaque fonction renvoie un dict :
#   header     : 'centered' (logo + titre centrés) ou 'left' (mentions à gauche, titre centré dessous)
#   info       : lignes du tableau d'enregistrement, [(libellé, valeur), (libellé, valeur)]
#   info_style : 'boxed' (fond bleuté, grille) ou 'plain' (sans fond, trait en bas)
#   sections   : [(titre, [éléments…]), …]
#   closing    : éléments placés avant les signatures (facultatif)
#   signatures : [(libellé, nom, mention), …] — 2 ou 3 colonnes


def _registration_info(act, lang):
    L = _lettres(lang)
    drawn = timezone.localtime(act.act_datetime)
    return [
        [(_t(lang, 'Région', 'Faritra'), act.region), (_t(lang, 'Acte N°', 'Laharana'), act.act_number)],
        [(_t(lang, 'District', 'Distrika'), act.district),
         (_t(lang, "Date de l'acte", 'Daty nanoratana'), L.date_short(drawn))],
        [(_t(lang, 'Commune', 'Kaominina'), _commune(act, lang)),
         (_t(lang, "Heure d'enregistrement", 'Ora nanoratana'), L.time(drawn))],
    ]


def _seal(lang):
    return _t(lang, '[Signature et sceau de la Mairie]', "[Sonia sy tombo-kasen'ny Kaominina]")


def _birth(act, s, lang):
    from .models import Sex

    L = _lettres(lang)
    birth = timezone.localtime(act.birth_datetime)
    drawn = timezone.localtime(act.act_datetime)
    female = act.child_sex == Sex.FEMALE
    father = (
        _person(lang, _t(lang, 'PÈRE', 'RAY'), act.father_full_name, False, act.father_birth_place,
                act.father_birth_date, act.father_profession, act.father_address)
        if act.father_full_name else _t(lang, '<b>PÈRE :</b> non déclaré.', '<b>RAY :</b> tsy voalaza.')
    )
    mother = _person(lang, _t(lang, 'MÈRE', 'RENY'), act.mother_full_name, True, act.mother_birth_place,
                     act.mother_birth_date, act.mother_profession, act.mother_address)
    commune = escape(_commune(act, lang))
    if lang == 'mg':
        child = (
            f"Tamin'ny {_b(L.date(birth))} tamin'ny {_b(L.time(birth))}, dia teraka tao {escape(act.birth_place)} "
            f"ny zaza {_b('vavy' if female else 'lahy')} atao hoe {_b(act.child_first_names)}, "
            f'anaram-pianakaviana {_b(act.child_last_name.upper())}.'
        )
        relationship = f', {escape(act.declarant_relationship)}' if act.declarant_relationship else ''
        declaration = (
            f"Nambaran'i {escape(act.declarant_name)}{relationship}, teo anatrehan'ny mpiandraikitra ny "
            f"fiankohonana, ny fahaterahana. Nosoratana tamin'ny {L.date(drawn)} tamin'ny {L.time(drawn)} "
            f'ity sora-pahaterahana ity, nataonay {_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))} '
            f'ao amin\'ny {commune}.'
        )
    else:
        child = (
            f'Le {_b(L.date(birth))} à {_b(L.time(birth))}, '
            f"est {'née' if female else 'né'} à {escape(act.birth_place)}, "
            f"{'une' if female else 'un'} enfant de sexe {_b('féminin' if female else 'masculin')} "
            f"{'prénommée' if female else 'prénommé'} {_b(act.child_first_names)}, "
            f'nom de famille {_b(act.child_last_name.upper())}.'
        )
        declaration = (
            f'La naissance a été déclarée par {escape(act.declarant_name)}, {escape(act.declarant_relationship)}, '
            "en présence de l'officier d'état civil. "
            f"L'acte a été dressé le {L.date(drawn)} à {L.time(drawn)} par nous, "
            f'{_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))} de la {commune}.'
        )
    return {
        'info': _registration_info(act, lang),
        'sections': [
            (_t(lang, "INFORMATIONS SUR L'ENFANT", 'MOMBA NY ZAZA'), [Paragraph(child, s['body'])]),
            (_t(lang, 'FILIATION', 'RAY AMAN-DRENY'),
             [Paragraph(father, s['body']), Spacer(1, 3 * mm), Paragraph(mother, s['body'])]),
            (_t(lang, 'DÉCLARATION ET DÉLIVRANCE', 'FANAMBARANA SY FANOMEZANA'), [Paragraph(declaration, s['body'])]),
            (_t(lang, 'MENTIONS MARGINALES', 'FANAMARIHANA AN-TSISINY'), [Paragraph(
                escape(_std(lang, act.marginal_notes) or _t(lang, 'Sans objet.', 'Tsy misy.')), s['notes'])]),
        ],
        'signatures': [
            (_t(lang, 'Le déclarant,', 'Ny mpanambara,'), act.declarant_name, ''),
            (_t(lang, "L'Officier d'État Civil,", "Ny mpiandraikitra ny fiankohonana,"), act.registrar_name,
             _seal(lang)),
        ],
    }


def _parent(lang, name, profession, deceased=False, feminine=False):
    """« Jean MARTIN (Retraité) », « feue Marie MARTIN » (« Marie MARTIN (efa nodimandry) »)."""
    text = ''
    if deceased and lang != 'mg':
        text = 'feue ' if feminine else 'feu '
    text += escape(name)
    if profession:
        text += f' ({escape(profession)})'
    if deceased and lang == 'mg':
        text += ' (efa nodimandry)'
    return text


def _marriage(act, s, lang):
    L = _lettres(lang)
    married = timezone.localtime(act.marriage_datetime)
    drawn = timezone.localtime(act.act_datetime)

    def column(prefix, child_word):
        father = getattr(act, f'{prefix}_father_name')
        mother = getattr(act, f'{prefix}_mother_name')
        parents = [
            _parent(lang, father, getattr(act, f'{prefix}_father_profession')) if father else '',
            _parent(lang, mother, getattr(act, f'{prefix}_mother_profession')) if mother else '',
        ]
        parents = [p for p in parents if p]
        if not parents:
            filiation = _t(lang, 'Non renseignée', 'Tsy voalaza')
        elif lang == 'mg':
            filiation = "Zanak'i " + '<br/>sy '.join(parents)
        else:
            filiation = f'{child_word} de ' + '<br/>et de '.join(parents)
        birth_date = getattr(act, f'{prefix}_birth_date')
        return [
            (_t(lang, 'Nom', 'Anarana'), escape(getattr(act, f'{prefix}_last_name').upper())),
            (_t(lang, 'Prénoms', "Fanampin'anarana"), escape(getattr(act, f'{prefix}_first_names'))),
            (_t(lang, 'Date de naissance', 'Daty nahaterahana'), L.date_short(birth_date)),
            (_t(lang, 'Lieu de naissance', 'Toerana nahaterahana'), escape(getattr(act, f'{prefix}_birth_place'))),
            (_t(lang, 'Profession', 'Asa'), escape(getattr(act, f'{prefix}_profession') or '—')),
            (_t(lang, 'Domicile', 'Fonenana'), escape(getattr(act, f'{prefix}_address'))),
            (_t(lang, 'Filiation', 'Ray aman-dreny'), '<br/>' + filiation),
        ]

    left, right = column('husband', 'Fils'), column('wife', 'Fille')
    rows = [[Paragraph(_t(lang, '<b>ÉPOUX 1</b>', '<b>MPIVADY 1</b>'), s['cell']),
             Paragraph(_t(lang, '<b>ÉPOUX 2</b>', '<b>MPIVADY 2</b>'), s['cell'])]]
    for (label_1, value_1), (label_2, value_2) in zip(left, right):
        rows.append([
            Paragraph(f'<b>{label_1} :</b> {value_1}', s['cell_plain']),
            Paragraph(f'<b>{label_2} :</b> {value_2}', s['cell_plain']),
        ])
    spouses = Table(rows, colWidths=['50%', '50%'])
    spouses.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.6, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
    ]))

    witness_word = _t(lang, 'Témoin', 'Vavolombelona')
    witnesses = '<br/>'.join(
        f"• <b>{witness_word} {index} :</b> {escape(name)}{', ' + escape(details) if details else ''}."
        for index, (name, details) in enumerate(
            ((act.witness1_name, act.witness1_details), (act.witness2_name, act.witness2_details)), start=1)
    )
    if lang == 'mg':
        celebration = [
            Paragraph(
                f"Natao ampahibemaso tao {escape(act.marriage_place)} ny fanambadiana, tamin'ny "
                f"{_b(L.date_short(married))} tamin'ny {_b(L.time_digits(married))}, teo anatrehanay "
                f'{_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))}.', s['body']),
            Spacer(1, 1.5 * mm),
            Paragraph(
                'Nanambara tsirairay avy ireo hivady fa samy maniry ho mpivady, ary nambaranay, '
                "amin'ny anaran'ny lalàna, fa mpivady izy ireo.", s['body']),
            Spacer(1, 1.5 * mm),
            Paragraph(f"<b>Fitsipika momba ny fananan'ny mpivady :</b> {escape(act.matrimonial_regime)}", s['body']),
        ]
    else:
        celebration = [
            Paragraph(
                f'Le mariage a été célébré publiquement à {escape(act.marriage_place)} '
                f'le {_b(L.date_short(married))} à {_b(L.time_digits(married))} devant nous, '
                f'{_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))}.', s['body']),
            Spacer(1, 1.5 * mm),
            Paragraph(
                "Les futurs époux ont déclaré l'un après l'autre vouloir se prendre pour époux, "
                "et nous avons prononcé, au nom de la loi, qu'ils sont unis par le mariage.", s['body']),
            Spacer(1, 1.5 * mm),
            Paragraph(f'<b>Régime matrimonial :</b> {escape(act.matrimonial_regime)}', s['body']),
        ]
    sections = [
        (_t(lang, 'LES ÉPOUX', 'NY MPIVADY'), [spouses]),
        (_t(lang, 'CÉLÉBRATION ET CONDITIONS LÉGALES', 'FANKALAZANA SY FEPETRA ARA-DALÀNA'), celebration),
        (_t(lang, 'LES TÉMOINS', 'NY VAVOLOMBELONA'), [Paragraph(witnesses, s['body'])]),
    ]
    from .models import DEFAULT_MARGINAL_NOTES

    if act.marginal_notes and act.marginal_notes != DEFAULT_MARGINAL_NOTES:
        sections.append((_t(lang, 'MENTIONS MARGINALES', 'FANAMARIHANA AN-TSISINY'),
                         [Paragraph(escape(_std(lang, act.marginal_notes)), s['notes'])]))
    return {
        'info': [
            [(_t(lang, 'Région', 'Faritra'), act.region), (_t(lang, 'Acte N°', 'Laharana'), act.act_number)],
            [(_t(lang, 'District', 'Distrika'), act.district),
             (_t(lang, "Date de l'acte", 'Daty nanoratana'), L.date_short(drawn))],
            [(_t(lang, 'Commune', 'Kaominina'), _commune(act, lang)), (_t(lang, 'Heure', 'Ora'), L.time_digits(drawn))],
        ],
        'sections': sections,
        'signatures': [
            (_t(lang, "Signature de l'Époux 1", "Sonian'ny mpivady 1"),
             f'{act.husband_first_names} {act.husband_last_name.upper()}', ''),
            (_t(lang, "Signature de l'Époux 2", "Sonian'ny mpivady 2"),
             f'{act.wife_first_names} {act.wife_last_name.upper()}', ''),
            (_t(lang, "L'Officier de l'état civil", 'Ny mpiandraikitra ny fiankohonana'),
             _t(lang, f'(Signé : {act.registrar_name})', f'(Nanao sonia : {act.registrar_name})'), _seal(lang)),
        ],
    }


MG_MARITAL_STATUS = {
    'SINGLE': 'Tokan-tena', 'MARRIED': 'Manambady', 'WIDOWED': 'Maty vady', 'DIVORCED': 'Nisara-panambadiana',
}


def _death(act, s, lang):
    from .models import Sex

    L = _lettres(lang)
    died = timezone.localtime(act.death_datetime)
    drawn = timezone.localtime(act.act_datetime)
    female = act.deceased_sex == Sex.FEMALE
    e = 'e' if female else ''
    name = _b(act.deceased_first_names + ' ' + act.deceased_last_name.upper())

    parents = []
    if act.father_name:
        parents.append(_parent(lang, act.father_name, '', act.father_deceased))
    if act.mother_name:
        parents.append(_parent(lang, act.mother_name, '', act.mother_deceased, feminine=True))

    if lang == 'mg':
        text = (
            f"Tamin'ny {_b(L.date_short(died))} tamin'ny {L.time_with_and(died)}, dia maty tao "
            f"{escape(act.death_place)} i {name}, "
            f"{escape(act.deceased_profession) if act.deceased_profession else 'tsy nanana asa'}"
        )
        if act.deceased_birth_date or act.deceased_birth_place:
            text += ', teraka'
            if act.deceased_birth_date:
                text += f" tamin'ny {L.date_short(act.deceased_birth_date)}"
            if act.deceased_birth_place:
                text += f' tao {escape(act.deceased_birth_place)}'
        if act.age_at_death is not None:
            text += f', {act.age_at_death} taona'
        text += f', nonina tao {escape(act.deceased_address)}.'
        if parents:
            text += " Zanak'i " + ' sy '.join(parents) + '.'
        if act.marital_status:
            text += f' {MG_MARITAL_STATUS.get(act.marital_status, act.get_marital_status_display())}'
            if act.spouse_name:
                text += f" (vady : {escape(act.spouse_name)})"
            text += '.'

        declarant = _b(act.declarant_name)
        if act.declarant_age:
            declarant += f', {act.declarant_age} taona'
        if act.declarant_profession:
            declarant += f', {escape(act.declarant_profession)}'
        if act.declarant_address:
            declarant += f', monina ao {escape(act.declarant_address)}'
        declarant += f', {escape(act.declarant_relationship)}'
        declaration = (
            f'Nosoratana sy nohamarininay {_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))} ao amin\'ny '
            f"{escape(_commune(act, lang))}, ny fahafatesana, araka ny fanambaran'i {declarant}, izay nanao sonia "
            'niaraka taminay ity sora-pahafatesana ity rehefa novakiana taminy.'
        )
        closing = ("Dika mitovy amin'ny tany am-boalohany.<br/>"
                   f"Natao teto {escape(act.place_name)}, tamin'ny {L.date_short(drawn)}.")
    else:
        text = (
            f'Le {_b(L.date_short(died))} à {L.time_with_and(died)}, est décédé{e} '
            f'à {escape(act.death_place)}, {name}, '
            f'{escape(act.deceased_profession) if act.deceased_profession else "sans profession"}'
        )
        if act.deceased_birth_date or act.deceased_birth_place:
            text += f', né{e}'
            if act.deceased_birth_date:
                text += f' le {L.date_short(act.deceased_birth_date)}'
            if act.deceased_birth_place:
                text += f' à {escape(act.deceased_birth_place)}'
        if act.age_at_death is not None:
            text += f', âgé{e} de {act.age_at_death} an{"s" if act.age_at_death > 1 else ""}'
        text += f', domicilié{e} au {escape(act.deceased_address)}.'
        if parents:
            text += f" {'Fille' if female else 'Fils'} de " + ' et de '.join(parents) + '.'
        if act.marital_status:
            status = act.get_marital_status_display()
            if act.marital_status in ('MARRIED', 'WIDOWED', 'DIVORCED'):
                status = {'MARRIED': f'Marié{e}', 'WIDOWED': 'Veuve' if female else 'Veuf',
                          'DIVORCED': f'Divorcé{e}'}[act.marital_status]
            text += f' {status}'
            if act.spouse_name:
                text += f" de {escape(act.spouse_name)}"
            text += '.'

        declarant = _b(act.declarant_name)
        if act.declarant_age:
            declarant += f', âgé(e) de {act.declarant_age} ans'
        if act.declarant_profession:
            declarant += f', {escape(act.declarant_profession)}'
        if act.declarant_address:
            declarant += f', domicilié(e) à {escape(act.declarant_address)}'
        declarant += f', {escape(act.declarant_relationship)}'
        declaration = (
            f'Le décès a été dressé et constaté par Nous, {_b(act.registrar_name)}, '
            f'{escape(_std(lang, act.registrar_title))} de la {escape(act.commune)}, sur la déclaration de {declarant}, '
            'qui, lecture faite, a signé avec Nous le présent acte.'
        )
        closing = ("Certifié conforme à l'original.<br/>"
                   f'Fait à {escape(act.place_name)}, le {L.date_short(drawn)}.')

    return {
        'header': 'left',
        'info_style': 'plain',
        'info': [
            [(_t(lang, "N° d'acte", 'Laharana'), act.act_number), (_t(lang, 'Commune de', 'Kaominina'), act.place_name)],
            [(_t(lang, "Date de l'acte", 'Daty nanoratana'), L.date_short(drawn)),
             (_t(lang, 'District', 'Distrika'), act.district)],
        ],
        'sections': [
            (_t(lang, 'INFORMATIONS SUR LE DÉFUNT', 'MOMBA NY MATY'), [Paragraph(text, s['body'])]),
            (_t(lang, 'DÉCLARATION DU DÉCÈS', 'FANAMBARANA NY FAHAFATESANA'), [Paragraph(declaration, s['body'])]),
            (_t(lang, 'MENTIONS MARGINALES (Le cas échéant)', 'FANAMARIHANA AN-TSISINY (raha misy)'), [Paragraph(
                escape(_std(lang, act.marginal_notes) or _t(lang, 'Néant.', 'Tsy misy.')), s['notes'])]),
        ],
        'closing': [Paragraph(closing, s['body_left'])],
        'signatures': [
            (_t(lang, 'Le déclarant,', 'Ny mpanambara,'), act.declarant_name, _t(lang, '[Signature]', '[Sonia]')),
            (_t(lang, "L'Officier de l'état civil,", 'Ny mpiandraikitra ny fiankohonana,'), act.registrar_name,
             _t(lang, '[Signature et Sceau]', '[Sonia sy tombo-kase]')),
        ],
    }


def _legislation(act, s, lang):
    L = _lettres(lang)
    drawn = timezone.localtime(act.act_datetime)
    commune = escape(_commune(act, lang))
    if lang == 'mg':
        delivered = f"Nomena tamin'ny {L.date_short(drawn)}"
        if act.recipient_name:
            delivered += f" ho an'i {_b(act.recipient_name)}"
        reference = (f'{_b(act.get_text_type_display() + " laharana " + act.text_number)} '
                     f"tamin'ny {L.date_short(act.text_date)}, momba ny : {_b(act.subject)}.")
        certification = (
            f'Izahay {_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))} ao amin\'ny {commune}, '
            "dia manamarina fa mitovy amin'ny tany am-boalohany voatahiry ao amin'ny arisivan'ny Kaominina "
            f"ity sombin-tsoratra ity. {delivered}, mba hampiasaina amin'izay ilana azy."
        )
    else:
        delivered = f'Délivré le {L.date_short(drawn)}'
        if act.recipient_name:
            delivered += f' à {_b(act.recipient_name)}'
        reference = (f'{_b(act.get_text_type_display() + " N° " + act.text_number)} du '
                     f'{L.date_short(act.text_date)}, portant : {_b(act.subject)}.')
        certification = (
            f'Nous, {_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))} de la {commune}, '
            "certifions le présent extrait conforme à l'original conservé aux archives de la Commune. "
            f'{delivered}, pour servir et valoir ce que de droit.'
        )
    return {
        'info': _registration_info(act, lang),
        'sections': [
            (_t(lang, 'TEXTE DE RÉFÉRENCE', 'LAHATSORATRA IFOTORANA'), [Paragraph(reference, s['body'])]),
            (_t(lang, 'EXTRAIT', 'SOMBIN-TSORATRA'), [_paragraph(act.content)]),
            (_t(lang, 'CERTIFICATION', 'FANAMARINANA'), [Paragraph(certification, s['body'])]),
        ],
        'signatures': [(_t(lang, 'Le requérant,', 'Ny mpangataka,'), act.recipient_name or '', ''),
                       (f'{_std(lang, act.registrar_title)},', act.registrar_name, _seal(lang))],
    }


def _service(act, s, lang):
    L = _lettres(lang)
    holder = _b(act.holder_full_name)
    if act.holder_national_id:
        holder += _t(lang, f', titulaire de la CIN N° {escape(act.holder_national_id)}',
                     f', manana karapanondro laharana {escape(act.holder_national_id)}')
    if act.holder_address:
        holder += _t(lang, f', demeurant à {escape(act.holder_address)}', f', monina ao {escape(act.holder_address)}')
    rows = [
        (_t(lang, 'Référence', 'Laharana fanondroana'), act.reference),
        (_t(lang, 'Lieu / bien concerné', 'Toerana / fananana voakasika'), act.location),
        (_t(lang, 'Montant', 'Vola'), _amount(act.amount) if act.amount is not None else ''),
        (_t(lang, "Valable jusqu'au", 'Manan-kery hatramin\'ny'), L.date_short(act.valid_until) if act.valid_until else ''),
    ]
    details = '<br/>'.join(f'<b>{label} :</b> {escape(value)}' for label, value in rows if value)
    objet = [_paragraph(act.subject)]
    if details:
        objet += [Spacer(1, 2 * mm), Paragraph(details, s['body'])]
    commune = escape(_commune(act, lang))
    sections = [
        (_t(lang, 'SERVICE', 'SAMPANA'), [Paragraph(
            _t(lang, f'Service : {_b(act.get_service_display())} — Nature : {_b(act.nature)}',
               f'Sampana : {_b(act.get_service_display())} — Karazany : {_b(act.nature)}'), s['body'])]),
        (_t(lang, 'BÉNÉFICIAIRE', 'MPAHAZO'), [Paragraph(holder + '.', s['body'])]),
        (_t(lang, 'OBJET', 'ANTONY'), objet),
        (_t(lang, 'ATTESTATION', 'FANAMARINANA'), [Paragraph(_t(
            lang,
            f'Nous, {_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))} de la {commune}, '
            "attestons l'exactitude des informations ci-dessus. Le présent document est délivré "
            'pour servir et valoir ce que de droit.',
            f'Izahay {_b(act.registrar_name)}, {escape(_std(lang, act.registrar_title))} ao amin\'ny {commune}, '
            'dia manamarina fa marina ireo voalaza etsy ambony ireo. Omena ity taratasy ity '
            "mba hampiasaina amin'izay ilana azy."), s['body'])]),
    ]
    if act.observations:
        sections.append((_t(lang, 'OBSERVATIONS', 'FANAMARIHANA'), [Paragraph(escape(act.observations), s['notes'])]))
    return {
        'info': _registration_info(act, lang),
        'sections': sections,
        'signatures': [(_t(lang, 'Le bénéficiaire,', 'Ny mpahazo,'), act.holder_full_name, ''),
                       (f'{_std(lang, act.registrar_title)},', act.registrar_name, _seal(lang))],
    }


BUILDERS = {
    'BirthCertificate': _birth,
    'MarriageCertificate': _marriage,
    'DeathCertificate': _death,
    'LegislationExtract': _legislation,
    'ServiceCertificate': _service,
}


def _header(act, style, lang):
    s = STYLES
    title = _title(act, lang)
    logo = Image(str(LOGO), width=20 * mm, height=20 * mm) if LOGO.exists() else ''
    if style == 'left':
        # Mentions à gauche (« État civil »), logo à droite, puis le titre centré.
        block = [
            Paragraph("REPOBLIKAN'I MADAGASIKARA", s['country_left']),
            Paragraph('Fitiavana - Tanindrazana - Fandrosoana', s['motto_left']),
            Paragraph(_t(lang, 'ÉTAT CIVIL', 'FIANKOHONANA'), s['service_left']),
        ]
        top = Table([[block, logo]], colWidths=[None, 22 * mm])
        top.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
        return [top, Spacer(1, 4 * mm), Paragraph(escape(title), s['title'])]
    block = [
        Paragraph("REPOBLIKAN'I MADAGASIKARA", s['country']),
        Paragraph('Fitiavana - Tanindrazana - Fandrosoana', s['motto']),
        Paragraph(escape(title), s['title']),
        Paragraph(escape(_commune(act, lang).upper()), s['subtitle']),
    ]
    if not logo:
        return block
    table = Table([[logo, block, '']], colWidths=[22 * mm, None, 10 * mm])
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    return [table]


def _info_table(rows, style):
    s = STYLES
    data = [
        [Paragraph(f'<b>{escape(label)} :</b> {escape(str(value))}', s['cell_plain']) for label, value in row]
        for row in rows
    ]
    table = Table(data, colWidths=['50%', '50%'])
    if style == 'plain':
        table.setStyle(TableStyle([
            ('LINEBELOW', (0, -1), (-1, -1), 0.8, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
            ('LINEBELOW', (0, 0), (-1, -1), 0.6, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 5.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ]))
    return table


def _signatures(entries):
    s = STYLES
    width = f'{100 / len(entries):.4f}%'
    table = Table(
        [
            [Paragraph(escape(label), s['sign']) for label, _, _ in entries],
            # Place pour signer (un peu moins haute avec trois signataires).
            [Spacer(1, (8 if len(entries) > 2 else 11) * mm) for _ in entries],
            [Paragraph(
                (f'{escape(note)}<br/>' if note else '') + f'<b>{escape(name)}</b>', s['sign_note'])
             for _, name, note in entries],
        ],
        colWidths=[width] * len(entries),
    )
    table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.6, LINE),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return table


def document_pdf(act, lang='mg'):
    """Renvoie les octets du PDF du document officiel (tous guichets), en malgache par défaut ou en français.

    Imprimé par l'agent au guichet, après le scan du bon de retrait, puis signé et cacheté."""
    if lang not in LANGUAGES:
        lang = 'mg'
    # Libellés des listes (type de texte, service…) dans la langue du document.
    with translation.override(lang):
        return _build_pdf(act, lang)


def _build_pdf(act, lang):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
        title=f'{_title(act, lang).capitalize()} N° {act.act_number}', author=act.commune,
        subject=str(act._meta.verbose_name), creator='Mairy Project',
    )
    layout = BUILDERS[type(act).__name__](act, STYLES, lang)

    story = _header(act, layout.get('header', 'centered'), lang)
    story += [Spacer(1, 4 * mm), _info_table(layout['info'], layout.get('info_style', 'boxed'))]
    for heading, flowables in layout['sections']:
        story.append(Paragraph(heading, STYLES['heading']))
        story.extend(flowables)
    closing = layout.get('closing', [])
    if closing:
        story += [Spacer(1, 5 * mm), *closing]

    # Le document officiel ne porte ni QR code ni empreinte : sa valeur vient de la signature
    # manuscrite et du cachet apposés au guichet. Le QR code est réservé au bon de retrait (ticket_pdf).
    story.append(Spacer(1, 5 * mm))
    story.append(KeepTogether([_signatures(layout['signatures'])]))

    doc.build(story)
    return buffer.getvalue()


# -- Bon de retrait (ticket) -----------------------------------------------------------
# Petit ticket remis au citoyen quand sa demande est traitée. Il ne reproduit pas l'acte :
# il permet seulement à l'agent de retrouver la demande au guichet en scannant le QR code.
# La signature (HMAC-SHA256) n'y est pas imprimée : elle reste sur le serveur, qui la vérifie au scan.

TICKET_STYLES = {
    'country': ParagraphStyle('t_country', fontName='Helvetica-Bold', fontSize=9, leading=11,
                              textColor=NAVY, alignment=TA_CENTER),
    'commune': ParagraphStyle('t_commune', fontName='Helvetica', fontSize=8, leading=10,
                              textColor=GREY, alignment=TA_CENTER),
    'title': ParagraphStyle('t_title', fontName='Helvetica-Bold', fontSize=16, leading=19,
                            textColor=NAVY, alignment=TA_CENTER, spaceBefore=4),
    'warning': ParagraphStyle('t_warning', fontName='Helvetica-BoldOblique', fontSize=8.5, leading=11,
                              textColor=colors.HexColor('#b3261e'), alignment=TA_CENTER),
    'cell': ParagraphStyle('t_cell', fontName='Helvetica', fontSize=9, leading=11.5,
                           textColor=colors.HexColor('#333a46')),
    'help': ParagraphStyle('t_help', fontName='Helvetica', fontSize=8, leading=10.5,
                           textColor=GREY, alignment=TA_CENTER),
    'mono': ParagraphStyle('t_mono', fontName='Courier', fontSize=6.5, leading=8,
                           textColor=GREY, alignment=TA_CENTER),
}

# Personne concernée par l'acte, selon le type de document.
TICKET_NAMES = {
    'BirthCertificate': lambda a: f'{a.child_first_names} {a.child_last_name.upper()}',
    'MarriageCertificate': lambda a: (f'{a.husband_first_names} {a.husband_last_name.upper()} et '
                                      f'{a.wife_first_names} {a.wife_last_name.upper()}'),
    'DeathCertificate': lambda a: f'{a.deceased_first_names} {a.deceased_last_name.upper()}',
    'LegislationExtract': lambda a: a.recipient_name or '',
    'ServiceCertificate': lambda a: a.holder_full_name,
}


def ticket_pdf(act):
    """Renvoie les octets du bon de retrait (format A6), toujours rédigé en français.

    Lève BonDejaRetire si le document a déjà été retiré : le bon ne peut plus être téléchargé."""
    if is_retrieved(act):
        raise BonDejaRetire(f'Le document N° {act.act_number} a déjà été retiré au guichet.')
    with translation.override('fr'):
        return _build_ticket(act)


def _build_ticket(act):
    t = TICKET_STYLES
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A6, leftMargin=8 * mm, rightMargin=8 * mm, topMargin=7 * mm, bottomMargin=6 * mm,
        title=f'Bon de retrait N° {act.act_number}', author=act.commune, creator='Mairy Project',
    )
    name_of = TICKET_NAMES.get(type(act).__name__)
    name = name_of(act) if name_of else ''
    drawn = timezone.localtime(act.act_datetime)

    logo = Image(str(LOGO), width=12 * mm, height=12 * mm) if LOGO.exists() else ''
    story = []
    if logo:
        story.append(logo)
    story += [
        Paragraph("REPOBLIKAN'I MADAGASIKARA", t['country']),
        Paragraph(escape(act.commune.upper()), t['commune']),
        Paragraph('BON DE RETRAIT', t['title']),
        Paragraph('Ne vaut pas document officiel', t['warning']),
        Spacer(1, 3 * mm),
    ]

    rows = [
        ('Document', act.document_title.capitalize()),
        ('N°', act.act_number),
        ('Concerne', name),
        ('Date', lettres.date_short(drawn)),
    ]
    info = Table(
        [[Paragraph(f'<b>{escape(label)} :</b> {escape(str(value))}', t['cell'])] for label, value in rows if value],
        colWidths=['100%'],
    )
    info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story += [info, Spacer(1, 4 * mm)]

    qr = _qr_image(act.verification_url, 38 * mm)
    qr.hAlign = 'CENTER'
    story += [
        qr,
        Spacer(1, 3 * mm),
        Paragraph('Présentez ce bon au guichet de la mairie, avec votre pièce d\'identité, '
                  'pour retirer votre document officiel signé et cacheté.', t['help']),
        Spacer(1, 2 * mm),
        Paragraph(f'Identifiant : {act.id}', t['mono']),
    ]
    doc.build(story)
    return buffer.getvalue()
