import re
import requests
from decimal import Decimal
from django.contrib import messages
from django.db.models import Case, Count, IntegerField, Sum, When
from django.shortcuts import render, get_object_or_404, redirect
from catalog.models import Product, Category, Brand
from core.models import SiteSettings
from core.scrapers import scrape_hsn
from .models import InventoryLot, InventoryTransaction, InventoryUnit, WarehouseLocation
from .forms import LotReceiveForm, UnitProcessForm


# ── Lots ──────────────────────────────────────────────────────────────────────

def lot_list(request):
    lots = InventoryLot.objects.select_related('product', 'warehouse_location').annotate(units_processed=Count('units'))
    status_filter = request.GET.get('status')
    if status_filter:
        lots = lots.filter(status=status_filter)
    return render(request, 'inventory/lot_list.html', {
        'lots': lots,
        'status_filter': status_filter,
    })


def lot_create(request):
    if request.method == 'POST':
        form = LotReceiveForm(request.POST)
        if form.is_valid():
            lot = form.save()
            messages.success(request, f"Lot {lot.sku} received successfully.")
            return redirect('inventory:lot_detail', pk=lot.pk)
    else:
        form = LotReceiveForm()
    return render(request, 'inventory/lot_form.html', {'form': form, 'title': 'Receive New Lot'})


def lot_detail(request, pk):
    lot = get_object_or_404(InventoryLot.objects.select_related('product', 'warehouse_location'), pk=pk)
    units = lot.units.select_related('product').all()
    return render(request, 'inventory/lot_detail.html', {'lot': lot, 'units': units})


def lot_edit(request, pk):
    lot = get_object_or_404(InventoryLot, pk=pk)
    if request.method == 'POST':
        form = LotReceiveForm(request.POST, instance=lot)
        if form.is_valid():
            form.save()
            messages.success(request, f"Lot {lot.sku} updated.")
            return redirect('inventory:lot_detail', pk=lot.pk)
    else:
        form = LotReceiveForm(instance=lot)
    return render(request, 'inventory/lot_form.html', {'form': form, 'title': f'Edit Lot {lot.sku}', 'lot': lot})


# ── Units ─────────────────────────────────────────────────────────────────────

def unit_list(request):
    units = InventoryUnit.objects.select_related('product', 'source_lot', 'warehouse_location')
    status_filter = request.GET.get('status', 'available')
    units = units.filter(status=status_filter)

    # Optional drill-down filters from the Inventory Levels page
    product_id = request.GET.get('product_id')
    size = request.GET.get('size', '')
    color = request.GET.get('color', '')
    if product_id:
        units = units.filter(product_id=product_id, size=size, color=color)

    return render(request, 'inventory/unit_list.html', {
        'units': units,
        'status_filter': status_filter,
        'status_choices': InventoryUnit.STATUS_CHOICES,
    })


def inventory_levels(request):
    """
    'How many of this product/size/color do I have?' -- rolls qty up across
    all conditions, locations, and cost-overridden rows into one number per
    product+size+color. Drill-down happens via unit_list, which already
    shows condition/location/cost per row.
    """
    q = request.GET.get('q', '')
    show_all = request.GET.get('show_all') == '1'

    rows = (
        InventoryUnit.objects
        .values('product_id', 'product__name', 'size', 'color')
        .annotate(
            available_qty=Sum(Case(
                When(status='available', then='qty'),
                default=0, output_field=IntegerField(),
            )),
            reserved_qty=Sum(Case(
                When(status='reserved', then='qty'),
                default=0, output_field=IntegerField(),
            )),
        )
        .order_by('product__name', 'size', 'color')
    )
    if q:
        rows = rows.filter(product__name__icontains=q)
    if not show_all:
        rows = rows.filter(available_qty__gt=0)

    return render(request, 'inventory/level_list.html', {
        'rows': rows,
        'q': q,
        'show_all': show_all,
    })


def unit_create(request, lot_pk):
    """Add a processed item to a lot."""
    lot = get_object_or_404(InventoryLot, pk=lot_pk)

    # HTMX UPC lookup result passed as query param
    product_id = request.GET.get('product_id') or request.POST.get('product_id')
    product = None
    if product_id:
        product = Product.objects.filter(pk=product_id).first()

    if request.method == 'POST':
        upc = request.POST.get('upc', '').strip()
        hsn_item_number = request.POST.get('hsn_item_number', '').strip()
        product_name = request.POST.get('product_name', '').strip()
        category_id = request.POST.get('category_id')
        brand_id = request.POST.get('brand_id')
        description = request.POST.get('description', '')

        # Resolve or create product
        if not product and hsn_item_number:
            product = Product.objects.filter(hsn_item_number=hsn_item_number).first()
        if not product and upc:
            product = Product.objects.filter(upc=upc).first()
        if not product and product_name:
            category = Category.objects.filter(pk=category_id).first() if category_id else None
            brand = Brand.objects.filter(pk=brand_id).first() if brand_id else None
            product = Product.objects.create(
                name=product_name,
                upc=upc,
                hsn_item_number=hsn_item_number,
                category=category,
                brand=brand,
                description=description,
            )
        elif product:
            update_fields = []
            if description and not product.description:
                product.description = description
                update_fields.append('description')
            if hsn_item_number and not product.hsn_item_number:
                product.hsn_item_number = hsn_item_number
                update_fields.append('hsn_item_number')
            # HSN scraping doesn't reliably provide brand data, so backfill it
            # here too, not just at creation time -- brand is required below.
            if brand_id and not product.brand:
                brand = Brand.objects.filter(pk=brand_id).first()
                if brand:
                    product.brand = brand
                    update_fields.append('brand')
            if update_fields:
                product.save(update_fields=update_fields)

        if not product:
            messages.error(request, "Please identify the product before saving.")
            return redirect('inventory:unit_create', lot_pk=lot.pk)

        if not product.brand:
            messages.error(request, "Please select a brand before saving — it's used in the item's SKU.")
            return redirect('inventory:unit_create', lot_pk=lot.pk)

        form = UnitProcessForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.product = product
            unit.source_lot = lot
            # Default cost to lot's derived unit_cost unless overridden
            if not unit.cost_overridden:
                unit.unit_cost = lot.unit_cost
            incoming_qty = max(unit.qty or 1, 1)

            if unit.serial_number:
                # Serialized items are individually distinct -- never pool,
                # always their own row, qty fixed at 1.
                unit.qty = 1
                unit.save()
                target = unit
            else:
                # cost_overridden items never merge (in either direction) --
                # that's what protects a standout piece's manual cost from
                # being averaged away.
                existing = None
                if not unit.cost_overridden:
                    existing = InventoryUnit.objects.filter(
                        product=product,
                        size=unit.size,
                        color=unit.color,
                        condition_grade=unit.condition_grade,
                        warehouse_location=unit.warehouse_location,
                        status='available',
                        cost_overridden=False,
                        serial_number='',
                    ).first()

                if existing:
                    combined_qty = existing.qty + incoming_qty
                    existing.unit_cost = (
                        (existing.unit_cost * existing.qty) + (unit.unit_cost * incoming_qty)
                    ) / combined_qty
                    existing.qty = combined_qty
                    existing.source_lot = lot
                    existing.save()
                    target = existing
                else:
                    unit.qty = incoming_qty
                    unit.save()
                    target = unit

            InventoryTransaction.objects.create(
                transaction_type='receive',
                quantity_delta=incoming_qty,
                product=product,
                inventory_lot=lot,
                inventory_unit=target,
            )
            messages.success(request, f"Added {incoming_qty} to {target.sku} (now qty {target.qty}) in lot {lot.sku}.")
            # Stay on the same page for rapid multi-item entry
            return redirect('inventory:unit_create', lot_pk=lot.pk)
    else:
        form = UnitProcessForm(initial={'unit_cost': lot.unit_cost})

    return render(request, 'inventory/unit_form.html', {
        'form': form,
        'lot': lot,
        'product': product,
        'categories': Category.objects.filter(parent=None, is_active=True),
        'brands': Brand.objects.filter(is_active=True),
    })


# ── Item Lookup (HTMX) ────────────────────────────────────────────────────────

def upc_lookup(request):
    """
    HTMX endpoint: looks up a scanned HSN item number or UPC.
    Priority: 1) internal catalog  2) HSN scrape  3) UPCitemdb (feature-flagged off)
    """
    raw = request.GET.get('upc', '').strip()
    if not raw:
        return render(request, 'inventory/partials/upc_result.html', {})

    # HSN barcodes are 6-digit model codes; scanners may append extra chars.
    # Take the first 6 characters and require all digits before doing anything.
    code = raw[:6]
    if not code.isdigit():
        return render(request, 'inventory/partials/upc_result.html', {
            'upc': raw,
            'invalid_code': True,
        })

    categories = Category.objects.filter(parent=None, is_active=True)
    brands = Brand.objects.filter(is_active=True)

    # 1. Internal catalog — check HSN item number and UPC
    product = (
        Product.objects.filter(hsn_item_number=code).first()
        or Product.objects.filter(upc=code).first()
    )
    if product:
        return render(request, 'inventory/partials/upc_result.html', {
            'product': product,
            'source': 'catalog',
            'brands': brands,
        })

    # 2. HSN scrape (primary external source)
    hsn_data = scrape_hsn(code)

    if hsn_data:
        hsn_data['hsn_item_number'] = code
        return render(request, 'inventory/partials/upc_result.html', {
            'api_data': hsn_data,
            'upc': code,
            'source': 'hsn',
            'categories': categories,
            'brands': brands,
        })

    # 3. UPCitemdb fallback (optional, toggled from UI settings)
    api_data = {}
    if SiteSettings.get().enable_upc_api_lookup:
        try:
            resp = requests.get(
                'https://api.upcitemdb.com/prod/trial/lookup',
                params={'upc': code},
                timeout=5,
            )
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                if items:
                    item = items[0]
                    api_data = {
                        'title': item.get('title', ''),
                        'description': item.get('description', ''),
                        'brand': item.get('brand', ''),
                        'images': item.get('images', []),
                    }
        except Exception:
            pass

    return render(request, 'inventory/partials/upc_result.html', {
        'api_data': api_data if api_data else None,
        'upc': code,
        'source': 'upc_api' if api_data else None,
        'categories': categories,
        'brands': brands,
    })


# ── Warehouse Locations ────────────────────────────────────────────────────────

def location_list(request):
    locations = WarehouseLocation.objects.all()
    return render(request, 'inventory/location_list.html', {'locations': locations})


def location_create(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if code and name:
            loc, created = WarehouseLocation.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': description},
            )
            if created:
                messages.success(request, f"Location {loc.code} created.")
            else:
                messages.warning(request, f"Location {code} already exists.")
        return redirect('inventory:location_list')
    return render(request, 'inventory/location_form.html')
