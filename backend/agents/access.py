"""Contrôle d'accès de l'espace agent : un agent ne voit que son guichet."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .guichets import GUICHETS


def agent_profile(user):
    """Profil agent du compte, ou None (administrateur, compte sans rôle)."""
    if not user.is_authenticated:
        return None
    try:
        return user.agent_profile
    except AttributeError:  # RelatedObjectDoesNotExist hérite d'AttributeError
        return None


def home_url_for(user):
    """Page d'arrivée après connexion, selon le rôle ; None si le compte n'a pas de rôle."""
    if user.is_staff:
        return reverse('admin:index')
    profile = agent_profile(user)
    if profile is not None:
        return reverse('agents:dashboard', args=[profile.guichet])
    return None


def guichet_required(view):
    """
    Réserve une vue `(request, number, ...)` à l'agent du guichet `number`.

    Les superutilisateurs peuvent consulter tous les guichets ; un agent qui
    ouvre le guichet d'un autre reçoit une page « accès refusé » (403).
    """

    @login_required
    @wraps(view)
    def wrapper(request, number, *args, **kwargs):
        guichet = GUICHETS.get(number)
        if guichet is None:
            raise Http404('Guichet inconnu.')

        profile = agent_profile(request.user)
        if request.user.is_superuser:
            pass
        elif profile is None:
            # Administrateur sans rôle de guichet, ou compte sans rôle.
            if request.user.is_staff:
                return redirect('admin:index')
            return render(request, 'agents/forbidden.html', {'reason': 'no_role'}, status=403)
        elif profile.guichet != number:
            return render(
                request, 'agents/forbidden.html',
                {'reason': 'other_guichet', 'own_guichet': profile.guichet_info}, status=403,
            )

        request.guichet = guichet
        request.agent_profile = profile
        return view(request, number, *args, **kwargs)

    return wrapper
