"""Statistiques et graphiques du tableau de bord de l'administration."""
from datetime import datetime

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

MONTH_LABELS = [_('Jan'), _('Fév'), _('Mar'), _('Avr'), _('Mai'), _('Juin'), _('Juil'), _('Aoû'), _('Sep'), _('Oct'), _('Nov'), _('Déc')]


def month_start(dt, offset=0):
    """Premier jour (00:00, heure locale) du mois de ``dt`` décalé de ``offset`` mois."""
    index = dt.year * 12 + dt.month - 1 + offset
    return dt.replace(
        year=index // 12, month=index % 12 + 1, day=1, hour=0, minute=0, second=0, microsecond=0,
    )


def kpi(queryset, field, label, url=None):
    """Total du mois en cours comparé au mois précédent."""
    now = timezone.localtime()
    this_month = month_start(now)
    last_month = month_start(now, -1)
    current = queryset.filter(**{f'{field}__gte': this_month}).count()
    previous = queryset.filter(**{f'{field}__gte': last_month, f'{field}__lt': this_month}).count()
    if previous:
        change = round((current - previous) * 100 / previous, 1)
    else:
        change = 100.0 if current else 0.0
    return {
        'label': label,
        'value': current,
        'total': queryset.count(),
        'change': change,
        'up': change >= 0,
        'url': url,
    }


def monthly_counts(queryset, field, months=12):
    """Nombre d'objets par mois sur les ``months`` derniers mois (mois courant inclus)."""
    now = timezone.localtime()
    start = month_start(now, -(months - 1))
    rows = (
        queryset.filter(**{f'{field}__gte': start})
        .order_by()
        .annotate(month=TruncMonth(field))
        .values('month')
        .annotate(n=Count('pk'))
    )
    by_month = {}
    for row in rows:
        month = row['month']
        if isinstance(month, datetime):
            month = timezone.localtime(month) if timezone.is_aware(month) else month
        by_month[(month.year, month.month)] = row['n']

    series = []
    for i in range(months):
        m = month_start(now, -(months - 1) + i)
        series.append({'label': MONTH_LABELS[m.month - 1], 'value': by_month.get((m.year, m.month), 0)})
    return series


def line_chart(series, width=1000, height=260, pad_x=44, pad_top=20, pad_bottom=36):
    """Prépare une courbe lissée (SVG) à partir d'une liste ``{'label', 'value'}``."""
    values = [point['value'] for point in series]
    top = max(values + [1])
    # Arrondi « propre » de l'axe vertical.
    step = max(1, -(-top // 4))
    top = step * 4
    inner_w = width - 2 * pad_x
    inner_h = height - pad_top - pad_bottom
    count = max(len(series) - 1, 1)

    points = []
    for i, point in enumerate(series):
        x = pad_x + inner_w * i / count
        y = pad_top + inner_h * (1 - point['value'] / top)
        points.append({**point, 'x': round(x, 1), 'y': round(y, 1)})

    # Courbe de Catmull-Rom convertie en segments de Bézier cubiques
    # (points de contrôle bornés à l'axe pour ne jamais passer sous zéro).
    baseline = pad_top + inner_h
    path = ''
    if points:
        path = f"M{points[0]['x']},{points[0]['y']}"
        for i in range(len(points) - 1):
            p0 = points[i - 1] if i > 0 else points[i]
            p1, p2 = points[i], points[i + 1]
            p3 = points[i + 2] if i + 2 < len(points) else p2
            c1x = p1['x'] + (p2['x'] - p0['x']) / 6
            c1y = min(p1['y'] + (p2['y'] - p0['y']) / 6, baseline)
            c2x = p2['x'] - (p3['x'] - p1['x']) / 6
            c2y = min(p2['y'] - (p3['y'] - p1['y']) / 6, baseline)
            path += f" C{c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2['x']},{p2['y']}"

    grid = [
        {'y': round(pad_top + inner_h * i / 4, 1), 'value': top - step * i}
        for i in range(5)
    ]
    area = f"{path} L{points[-1]['x']},{baseline} L{points[0]['x']},{baseline} Z" if points else ''
    return {
        'width': width,
        'height': height,
        'points': points,
        'path': path,
        'area': area,
        'grid': grid,
        'label_y': height - 10,
        'x_min': pad_x,
        'x_max': width - pad_x,
        'total': sum(values),
    }


def breakdown(queryset, field, choices):
    """Répartition par valeur d'un champ à choix, avec pourcentage pour les barres."""
    counts = {
        row[field]: row['n']
        for row in queryset.order_by().values(field).annotate(n=Count('pk'))
    }
    total = sum(counts.values())
    rows = []
    for value, label in choices:
        n = counts.get(value, 0)
        rows.append({'label': label, 'value': n, 'percent': round(n * 100 / total) if total else 0})
    rows.sort(key=lambda row: row['value'], reverse=True)
    return {'rows': rows, 'total': total}
