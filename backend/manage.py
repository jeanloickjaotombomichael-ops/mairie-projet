#!/usr/bin/env python
"""Utilitaire en ligne de commande de Django pour le projet Mairy Project."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer Django. Avez-vous installé les dépendances "
            "(pip install -r requirements.txt) et activé votre environnement virtuel ?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
