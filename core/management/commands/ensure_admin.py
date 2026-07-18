import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Create the initial admin superuser from DJANGO_SUPERUSER_USERNAME / '
        'DJANGO_SUPERUSER_PASSWORD env vars, if that username does not already exist. '
        'Safe to run on every deploy.'
    )

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not username or not password:
            self.stdout.write('DJANGO_SUPERUSER_USERNAME/PASSWORD not set, skipping admin creation.')
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Admin user '{username}' already exists, skipping.")
            return

        User.objects.create_superuser(
            username=username,
            email=os.environ.get('DJANGO_SUPERUSER_EMAIL', ''),
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'."))
