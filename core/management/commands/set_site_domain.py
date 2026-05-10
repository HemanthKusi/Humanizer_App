"""
Management command to set the Django Sites domain.

Used during deployment to configure allauth's site domain
for Google OAuth callbacks.

Usage:
    python manage.py set_site_domain rewright.app
"""

from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Set the domain and name for Django Sites framework (used by allauth)'

    def add_arguments(self, parser):
        parser.add_argument('domain', type=str, help='The domain name (e.g., rewright.app)')
        parser.add_argument('--name', type=str, default='Rewright', help='The site display name')

    def handle(self, *args, **options):
        domain = options['domain']
        name = options['name']

        site = Site.objects.get(id=1)
        site.domain = domain
        site.name = name
        site.save()

        self.stdout.write(self.style.SUCCESS(f'Site updated: domain={domain}, name={name}'))