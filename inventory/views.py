import re
import requests
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect
from catalog.models import Product, Category, Brand
from core.models import SiteSettings
from core.scrapers import scrape_hsn
from .models import InventoryLot, InventoryUnit, WarehouseLocation
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
    return render(request, 'inventory/unit_list.html', {
        'units': units,
        'status_filter': status_filter,
        'status_choices': InventoryUnit.STATUS_CHOICES,
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
            if update_fields:
                product.save(update_fields=update_fields)

        if not product:
            messages.error(request, "Please identify the product before saving.")
            return redirect('inventory:unit_create', lot_pk=lot.pk)

        form = UnitProcessForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.product = product
            unit.source_lot = lot
            # Default cost to lot's derived unit_cost unless overridden
            if not unit.cost_overridden:
                unit.unit_cost = lot.unit_cost
            unit.save()
            messages.success(request, f"Item {unit.sku} added to lot {lot.sku}.")
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
