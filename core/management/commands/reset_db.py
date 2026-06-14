import os
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


SEED_CATEGORIES = [
    ('Apparel & Accessories', 'CLO', None),
    ('Electronics', 'ELC', None),
    ('Beauty & Personal Care', 'BTY', None),
    ('Home & Kitchen', 'HOM', None),
    ('Jewelry & Watches', 'JWL', None),
    ('Health & Wellness', 'HLT', None),
    ('Toys & Games', 'TOY', None),
    ('Sports & Outdoors', 'SPT', None),
    ('Food & Grocery', 'FGR', None),
    ('Other', 'OTH', None),
]


class Command(BaseCommand):
    help = 'Reset the SQLite database: delete, re-migrate, and seed base data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip confirmation prompt.',
        )
        parser.add_argument(
            '--no-seed',
            action='store_true',
            help='Skip seeding categories after reset.',
        )

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES['default']['NAME'])

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                f'\nThis will DELETE {db_path} and all data inside it.'
            ))
            confirm = input('Type "yes" to continue: ').strip().lower()
            if confirm != 'yes':
                self.stdout.write('Aborted.')
                return

        # Delete the database file
        if db_path.exists():
            os.remove(db_path)
            self.stdout.write(self.style.SUCCESS(f'Deleted {db_path}'))
        else:
            self.stdout.write(f'{db_path} not found — skipping delete.')

        # Re-run all migrations
        self.stdout.write('Running migrations...')
        call_command('migrate', verbosity=0)
        self.stdout.write(self.style.SUCCESS('Migrations applied.'))

        # Seed base data
        if not options['no_seed']:
            self._seed_categories()

        self.stdout.write(self.style.SUCCESS('\nDatabase reset complete.'))

    def _seed_categories(self):
        from catalog.models import Category

        self.stdout.write('Seeding categories...')
        for name, prefix, parent_name in SEED_CATEGORIES:
            Category.objects.get_or_create(
                name=name,
                defaults={'sku_prefix': prefix, 'is_active': True},
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(SEED_CATEGORIES)} categories seeded.'))
