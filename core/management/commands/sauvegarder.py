"""Exporte la base dans un fichier JSON horodaté.

Usage : ``python manage.py sauvegarder`` ou ``--output /chemin/backup.json``.
"""

import json
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Crée une sauvegarde logique de toutes les données (RG09)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            help='Chemin du fichier (défaut : backups/pharmagest-AAAAMMJJ-HHMMSS.json)',
        )

    def handle(self, *args, **options):
        destination = Path(options['output']) if options['output'] else (
            Path(settings.BASE_DIR) / 'backups' /
            f"pharmagest-{timezone.localtime():%Y%m%d-%H%M%S}.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)

        buffer = StringIO()
        call_command(
            'dumpdata', '--natural-foreign', verbosity=0,
            indent=2, stdout=buffer,
        )
        # On vérifie que la sauvegarde est du JSON valide avant de l'écrire.
        contenu = json.dumps(json.loads(buffer.getvalue()), ensure_ascii=False, indent=2)
        destination.write_text(contenu, encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(
            f'Sauvegarde créée : {destination} ({destination.stat().st_size} octets)'
        ))
        return str(destination)
