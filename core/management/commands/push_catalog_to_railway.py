import os

import dj_database_url
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from catalog.models import Brand, Category, Product

ENV_VAR = 'RAILWAY_DATABASE_URL'
ALIAS = 'railway'


class Command(BaseCommand):
    help = (
        'Push Category/Brand/Product catalog data from the local database to '
        'Railway (or any DB reachable via RAILWAY_DATABASE_URL). Only fills in '
        'missing rows/fields -- never overwrites data already present there, '
        'since local is the only place the HSN scraper actually runs but the '
        'Railway copy may have been corrected by hand.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt.')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without writing anything.')

    def handle(self, *args, **options):
        url = os.environ.get(ENV_VAR)
        if not url:
            raise CommandError(
                f'{ENV_VAR} is not set. Get a connection string for the target database '
                '(for Railway Postgres: Settings > Networking > enable Public Networking on '
                'the Postgres service, then copy the connection string from its Connect tab) '
                f'and set it as an env var named {ENV_VAR}.'
            )

        db_config = dj_database_url.parse(url, conn_max_age=0, ssl_require='sqlite' not in url)
        settings.DATABASES[ALIAS] = db_config
        # ConnectionHandler caches its processed settings (defaults like
        # TIME_ZONE/OPTIONS get filled in once, on first access). Adding an
        # alias afterwards means it never goes through that step unless the
        # cache is cleared so it re-processes settings.DATABASES from scratch.
        try:
            del connections.settings
        except AttributeError:
            pass
        try:
            connections[ALIAS].ensure_connection()
        except Exception as exc:
            raise CommandError(f'Could not connect to {ENV_VAR}: {exc}')

        dry_run = options['dry_run']
        if not dry_run and not options['yes']:
            self.stdout.write(self.style.WARNING(
                '\nThis will write Category/Brand/Product data from your LOCAL database '
                'into the database at RAILWAY_DATABASE_URL. Existing data there is never '
                'overwritten -- only missing rows/fields are filled in.'
            ))
            confirm = input('Type "yes" to continue: ').strip().lower()
            if confirm != 'yes':
                self.stdout.write('Aborted.')
                return

        stats = {'categories': 0, 'brands': 0, 'products': 0, 'skipped': 0}

        # Categories: parents before children (shallow tree -- sku_prefix's own
        # help text already assumes only top-level categories carry a prefix).
        for cat in Category.objects.filter(parent__isnull=True).order_by('id'):
            self._sync_category(cat, dry_run, stats)
        for cat in Category.objects.filter(parent__isnull=False).order_by('id'):
            self._sync_category(cat, dry_run, stats)

        for brand in Brand.objects.order_by('id'):
            self._sync_brand(brand, dry_run, stats)

        for product in Product.objects.select_related('brand', 'category').order_by('id'):
            self._sync_product(product, dry_run, stats)

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f"\n{prefix}Categories touched: {stats['categories']} | "
            f"Brands touched: {stats['brands']} | "
            f"Products touched: {stats['products']} | "
            f"Products skipped (no HSN#/UPC to match on): {stats['skipped']}"
        ))

    def _sync_category(self, cat, dry_run, stats):
        existing = Category.objects.using(ALIAS).filter(name=cat.name).first()
        parent_remote = None
        if cat.parent:
            parent_remote = Category.objects.using(ALIAS).filter(name=cat.parent.name).first()

        if existing:
            changed = []
            if not existing.sku_prefix and cat.sku_prefix:
                existing.sku_prefix = cat.sku_prefix
                changed.append('sku_prefix')
            if changed:
                if not dry_run:
                    existing.save(using=ALIAS, update_fields=changed)
                stats['categories'] += 1
                self.stdout.write(f"  category updated: {cat.name} ({', '.join(changed)})")
        else:
            if not dry_run:
                Category.objects.using(ALIAS).create(
                    name=cat.name, sku_prefix=cat.sku_prefix,
                    parent=parent_remote, is_active=cat.is_active,
                )
            stats['categories'] += 1
            self.stdout.write(f"  category created: {cat.name}")

    def _sync_brand(self, brand, dry_run, stats):
        existing = Brand.objects.using(ALIAS).filter(name=brand.name).first()
        if existing:
            return
        if not dry_run:
            Brand.objects.using(ALIAS).create(name=brand.name, is_active=brand.is_active)
        stats['brands'] += 1
        self.stdout.write(f"  brand created: {brand.name}")

    def _sync_product(self, product, dry_run, stats):
        if product.hsn_item_number:
            lookup = {'hsn_item_number': product.hsn_item_number}
        elif product.upc:
            lookup = {'upc': product.upc}
        else:
            stats['skipped'] += 1
            self.stdout.write(self.style.WARNING(f"  product skipped (no HSN#/UPC): {product.name}"))
            return

        category_remote = None
        if product.category:
            category_remote = Category.objects.using(ALIAS).filter(name=product.category.name).first()
        brand_remote = None
        if product.brand:
            brand_remote = Brand.objects.using(ALIAS).filter(name=product.brand.name).first()

        existing = Product.objects.using(ALIAS).filter(**lookup).first()
        if existing:
            changed = []
            for field in ('name', 'description', 'mpn', 'upc', 'hsn_item_number', 'images'):
                current = getattr(existing, field)
                incoming = getattr(product, field)
                if not current and incoming:
                    setattr(existing, field, incoming)
                    changed.append(field)
            if not existing.category and category_remote:
                existing.category = category_remote
                changed.append('category')
            if not existing.brand and brand_remote:
                existing.brand = brand_remote
                changed.append('brand')
            if changed:
                if not dry_run:
                    existing.save(using=ALIAS, update_fields=changed)
                stats['products'] += 1
                self.stdout.write(f"  product updated: {product.name} ({', '.join(changed)})")
        else:
            if not dry_run:
                Product.objects.using(ALIAS).create(
                    name=product.name, brand=brand_remote, category=category_remote,
                    description=product.description, upc=product.upc,
                    hsn_item_number=product.hsn_item_number, mpn=product.mpn,
                    images=product.images, is_active=product.is_active,
                )
            stats['products'] += 1
            self.stdout.write(f"  product created: {product.name}")