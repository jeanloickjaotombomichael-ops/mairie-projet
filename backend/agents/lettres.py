"""Nombres, dates et heures en toutes lettres (français), pour la rédaction des actes d'état civil."""

UNITS = [
    'zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix',
    'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize',
]
TENS = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante'}
MONTHS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def _under_100(n):
    if n < 17:
        return UNITS[n]
    if n < 20:
        return f'dix-{UNITS[n - 10]}'
    tens, unit = divmod(n, 10)
    if tens == 7:
        return 'soixante et onze' if n == 71 else f'soixante-{_under_100(n - 60)}'
    if tens == 8:
        return 'quatre-vingts' if unit == 0 else f'quatre-vingt-{UNITS[unit]}'
    if tens == 9:
        return f'quatre-vingt-{_under_100(n - 80)}'
    if unit == 0:
        return TENS[tens]
    if unit == 1:
        return f'{TENS[tens]} et un'
    return f'{TENS[tens]}-{UNITS[unit]}'


def _under_1000(n):
    hundreds, rest = divmod(n, 100)
    if hundreds == 0:
        return _under_100(rest)
    head = 'cent' if hundreds == 1 else f"{UNITS[hundreds]} cent{'s' if rest == 0 else ''}"
    return f'{head} {_under_100(rest)}' if rest else head


def number(n):
    """0 à 999 999 en toutes lettres (orthographe traditionnelle)."""
    thousands, rest = divmod(n, 1000)
    if thousands == 0:
        return _under_1000(rest)
    head = 'mille' if thousands == 1 else f'{_under_1000(thousands)} mille'
    return f'{head} {_under_1000(rest)}' if rest else head


def _feminine(words):
    """« un » → « une » en fin de nombre (heures, minutes : noms féminins)."""
    return f'{words[:-2]}une' if words == 'un' or words.endswith(' un') or words.endswith('-un') else words


def date(value):
    """« quinze mai deux mille vingt-six » (« premier » pour le 1er)."""
    day = 'premier' if value.day == 1 else number(value.day)
    return f'{day} {MONTHS[value.month - 1]} {number(value.year)}'


def date_short(value):
    """« 22 septembre 2026 »."""
    day = '1er' if value.day == 1 else str(value.day)
    return f'{day} {MONTHS[value.month - 1]} {value.year}'


def time(value):
    """« quatorze heures trente minutes », « une heure », « midi » n'est pas utilisé dans les actes."""
    hours = _feminine(number(value.hour))
    text = f"{hours} heure{'s' if value.hour > 1 else ''}"
    if value.minute:
        minutes = _feminine(number(value.minute))
        text += f" {minutes} minute{'s' if value.minute > 1 else ''}"
    return text


def time_digits(value):
    """« 14 heures 30 minutes » (« 9 heures » si minutes nulles)."""
    text = f"{value.hour} heure{'s' if value.hour > 1 else ''}"
    if value.minute:
        text += f" {value.minute} minute{'s' if value.minute > 1 else ''}"
    return text


def time_with_and(value):
    """« dix heures et trente minutes » (« dix heures » si minutes nulles)."""
    if not value.minute:
        return time(value)
    hours = _feminine(number(value.hour))
    minutes = _feminine(number(value.minute))
    return (f"{hours} heure{'s' if value.hour > 1 else ''} et "
            f"{minutes} minute{'s' if value.minute > 1 else ''}")
