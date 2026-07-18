from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from inventory.models import InventoryLot, InventoryUnit
from sales.models import Sale
from .decorators import manager_required
from .models import SiteSettings


@login_not_required
def healthcheck(request):
    return HttpResponse("ok")


def dashboard(request):
    today = timezone.now().date()

    today_sales = Sale.objects.filter(sale_date__date=today)
    gross_today = sum(s.gross_amount for s in today_sales)
    net_today = sum(s.net_amount_received for s in today_sales)

    units_available = InventoryUnit.objects.filter(status='available').count()
    lots_pending = InventoryLot.objects.filter(status='pending_processing').count()
    total_lots = InventoryLot.objects.count()

    context = {
        'gross_today': gross_today,
        'net_today': net_today,
        'units_available': units_available,
        'lots_pending': lots_pending,
        'total_lots': total_lots,
        'today': today,
    }
    return render(request, 'core/dashboard.html', context)


@manager_required
def site_settings(request):
    config = SiteSettings.get()
    if request.method == 'POST':
        config.enable_upc_api_lookup = 'enable_upc_api_lookup' in request.POST
        config.save()
        messages.success(request, "Settings saved.")
        return redirect('site_settings')
    return render(request, 'core/settings.html', {'config': config})
