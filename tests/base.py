"""Classe de base commune : initialise les groupes et permissions des rôles."""

from django.core.management import call_command
from django.test import TestCase


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
