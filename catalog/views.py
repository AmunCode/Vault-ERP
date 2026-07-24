from django.shortcuts import get_object_or_404, render
from .models import Product


def product_list(request):
    q = request.GET.get('q', '')
    products = Product.objects.select_related('brand', 'category').filter(is_active=True)
    if q:
        products = products.filter(name__icontains=q)
    return render(request, 'catalog/product_list.html', {'products': products, 'q': q})


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('brand', 'category'), pk=pk)
    units = product.inventory_units.select_related('warehouse_location').order_by('-created_at')
    return render(request, 'catalog/product_detail.html', {'product': product, 'units': units})
