"""Restaure une sauvegarde créée par ``sauvegarder``.

Usage : ``python manage.py restaurer backups/pharmagest-....json``.

La restauration est transactionnelle : en cas d'erreur, aucune donnée n'est
partiellement écrite. Une sauvegarde de sécurité est créée avant l'opération.
"""

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Restaure une sauvegarde JSON (test de reprise après incident)'

    def add_arguments(self, parser):
        parser.add_argument('fichier', help='Chemin vers le fichier JSON de sauvegarde')

    def handle(self, *args, **options):
        source = Path(options['fichier'])
        if not source.is_file():
            raise CommandError(f'Fichier introuvable : {source}')

        call_command('sauvegarder', output=str(source.with_suffix('.avant-restauration.json')),
                     verbosity=0)
        self.stdout.write('Sauvegarde de sécurité créée avant restauration.')

        with transaction.atomic():
            call_command('loaddata', str(source), verbosity=0)

        self.stdout.write(self.style.SUCCESS(
            f'Données restaurées depuis {source}.'
        ))
