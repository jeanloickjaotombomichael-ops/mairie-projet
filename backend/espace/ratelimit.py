"""Limitation de débit générique, basée sur le cache Django."""
from django.core.cache import cache


def is_rate_limited(key, limit, window):
    """Compte un appel pour ``key`` et indique si ``limit`` appels sont dépassés.

    ``window`` est la durée de la fenêtre, en secondes. Le compteur est créé au
    premier appel puis incrémenté ; il expire tout seul à la fin de la fenêtre.
    """
    cache.add(key, 0, timeout=window)
    try:
        count = cache.incr(key)
    except ValueError:  # la clé a expiré entre add() et incr()
        cache.set(key, 1, timeout=window)
        count = 1
    return count > limit
