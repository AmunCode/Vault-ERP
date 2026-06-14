from django.shortcuts import render
from .models import Product


def product_list(request):
    q = request.GET.get('q', '')
    products = Product.objects.select_related('brand', 'category').filter(is_active=True)
    if q:
        products = products.filter(name__icontains=q)
    return render(request, 'catalog/product_list.html', {'products': products, 'q': q})
