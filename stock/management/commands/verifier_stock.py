"""Controle de coherence entre quantites stockees et mouvements."""

from django.core.management.base import BaseCommand

from stock.services import verifier_integrite


class Command(BaseCommand):
    help = 'Verifie que chaque lot correspond a la somme de ses mouvements'

    def handle(self, *args, **options):
        incoherences = verifier_integrite()
        if not incoherences:
            self.stdout.write(self.style.SUCCESS('Stock coherent : aucune incoherence.'))
            return
        for lot, stocke, calcule in incoherences:
            self.stderr.write(
                f'{lot} : stocke={stocke}, calcule={calcule}'
            )
        self.stderr.write(f'{len(incoherences)} lot(s) incoherent(s).')
