from django.contrib import admin
from .models import Sale, SaleLineItem


class SaleLineItemInline(admin.TabularInline):
    model = SaleLineItem
    extra = 0
    fields = ('product', 'inventory_lot', 'inventory_unit', 'quantity', 'sale_price', 'allocated_cost')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'sale_date', 'marketplace', 'status', 'gross_amount', 'net_amount_received')
    list_filter = ('marketplace', 'status')
    search_fields = ('order_number', 'customer_name')
    inlines = [SaleLineItemInline]


@admin.register(SaleLineItem)
class SaleLineItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'sale', 'quantity', 'sale_price', 'allocated_cost')
    search_fields = ('product__name',)
