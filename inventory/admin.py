from django.contrib import admin
from .models import WarehouseLocation, InventoryLot, InventoryUnit, InventoryTransaction

# Register your models here.
@admin.register(WarehouseLocation)
class WarehouseLocationAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)

@admin.register(InventoryLot)
class InventoryLotAdmin(admin.ModelAdmin):
    list_display = (
    'sku',
    'product',
    'quantity_on_hand',
    'quantity_reserved',
    'quantity_available',
    'unit_cost',
    'condition_grade',
    'warehouse_location'
   )
    search_fields = ('sku', 'product__name')
    list_filter = ('condition_grade', 'warehouse_location')

@admin.register(InventoryUnit)
class InventoryUnitAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'condition_grade', 'status')
    search_fields = ('serial_number', 'sku')
    list_filter = ('status',)

@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'product', 'quantity_delta', 'created_at')
    search_fields = ('inventory_lot__sku',)
    list_filter = ('transaction_type', 'created_at')
