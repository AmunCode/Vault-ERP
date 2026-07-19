import os
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections


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
        parser.add_argument(
            '--keep-users',
            action='store_true',
            help='Preserve existing user accounts (and their group memberships) across the reset.',
        )

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES['default']['NAME'])

        saved_users = []
        if options['keep_users']:
            saved_users = self._save_users()

        if not options['yes']:
            warning = f'\nThis will DELETE {db_path} and all data inside it.'
            if options['keep_users']:
                warning += f' ({len(saved_users)} user account(s) will be restored afterward.)'
            self.stdout.write(self.style.WARNING(warning))
            confirm = input('Type "yes" to continue: ').strip().lower()
            if confirm != 'yes':
                self.stdout.write('Aborted.')
                return

        # Release any open connection first -- on Windows, a file with an open
        # handle (e.g. from the --keep-users query above) can't be deleted.
        connections['default'].close()

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

        if options['keep_users']:
            self._restore_users(saved_users)

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

    def _save_users(self):
        from django.contrib.auth.models import User

        self.stdout.write('Saving existing user accounts...')
        saved = [
            {
                'username': user.username,
                'password': user.password,  # already-hashed -- copied as-is, not re-hashed
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'is_active': user.is_active,
                'date_joined': user.date_joined,
                'groups': list(user.groups.values_list('name', flat=True)),
            }
            for user in User.objects.all()
        ]
        self.stdout.write(self.style.SUCCESS(f'  Saved {len(saved)} user account(s).'))
        return saved

    def _restore_users(self, saved_users):
        from django.contrib.auth.models import Group, User

        self.stdout.write('Restoring user accounts...')
        for data in saved_users:
            group_names = data.pop('groups')
            user = User.objects.create(**data)
            if group_names:
                user.groups.set(Group.objects.filter(name__in=group_names))
        self.stdout.write(self.style.SUCCESS(f'  Restored {len(saved_users)} user account(s).'))
