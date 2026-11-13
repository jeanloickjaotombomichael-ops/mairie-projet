"""Nombres, dates et heures en toutes lettres (malgache), pour la rédaction des actes d'état civil.

Même interface que `lettres` (français). En malgache, un nombre se lit des unités vers les milliers :
1999 → « sivy amby sivifolo sy sivinjato sy arivo », 2026 → « enina amby roapolo sy roa arivo ».
"""

UNITS = ['aotra', 'iray', 'roa', 'telo', 'efatra', 'dimy', 'enina', 'fito', 'valo', 'sivy']
TENS = {
    1: 'folo', 2: 'roapolo', 3: 'telopolo', 4: 'efapolo', 5: 'dimampolo',
    6: 'enimpolo', 7: 'fitopolo', 8: 'valopolo', 9: 'sivifolo',
}
HUNDREDS = {
    1: 'zato', 2: 'roanjato', 3: 'telonjato', 4: 'efajato', 5: 'dimanjato',
    6: 'eninjato', 7: 'fitonjato', 8: 'valonjato', 9: 'sivinjato',
}
MONTHS = [
    'Janoary', 'Febroary', 'Martsa', 'Aprily', 'Mey', 'Jona',
    'Jolay', 'Aogositra', 'Septambra', 'Oktobra', 'Novambra', 'Desambra',
]


def _under_100(n):
    if n < 10:
        return UNITS[n]
    tens, unit = divmod(n, 10)
    if unit == 0:
        return TENS[tens]
    # « iraika » remplace « iray » devant « amby » / « ambin'ny ».
    head = 'iraika' if unit == 1 else UNITS[unit]
    if tens == 1:
        return f"{head} ambin'ny folo"
    return f'{head} amby {TENS[tens]}'


def _under_1000(n):
    hundreds, rest = divmod(n, 100)
    if hundreds == 0:
        return _under_100(rest)
    return f'{_under_100(rest)} sy {HUNDREDS[hundreds]}' if rest else HUNDREDS[hundreds]


def number(n):
    """0 à 999 999 en toutes lettres, des unités vers les milliers."""
    thousands, rest = divmod(n, 1000)
    if thousands == 0:
        return _under_1000(rest)
    head = 'arivo' if thousands == 1 else f'{_under_1000(thousands)} arivo'
    return f'{_under_1000(rest)} sy {head}' if rest else head


def date(value):
    """« dimy ambin'ny folo Mey, enina amby roapolo sy roa arivo » (« voalohany » pour le 1er)."""
    day = 'voalohany' if value.day == 1 else number(value.day)
    return f'{day} {MONTHS[value.month - 1]}, {number(value.year)}'


def date_short(value):
    """« 22 Septambra 2026 »."""
    return f'{value.day} {MONTHS[value.month - 1]} {value.year}'


def time(value):
    """« efatra ambin'ny folo ora sy telopolo minitra »."""
    text = f'{number(value.hour)} ora'
    if value.minute:
        text += f' sy {number(value.minute)} minitra'
    return text


def time_digits(value):
    """« 14 ora sy 30 minitra » (« 9 ora » si minutes nulles)."""
    text = f'{value.hour} ora'
    if value.minute:
        text += f' sy {value.minute} minitra'
    return text


def time_with_and(value):
    """Même rédaction que `time` : le malgache relie déjà heures et minutes par « sy »."""
    return time(value)
