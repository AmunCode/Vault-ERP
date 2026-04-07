from django.db import models
from catalog.models import Product

# Create your models here.
class WarehouseLocation(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"
    

from catalog.models import Product


class InventoryLot(models.Model):
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used_like_new', 'Used - Like New'),
        ('used_good', 'Used - Good'),
        ('used_fair', 'Used - Fair'),
        ('for_parts', 'For Parts / Not Working'),
        ('donate', 'Donate'),
        ('dispose', 'Dispose'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_lots')
    sku = models.CharField(max_length=100, unique=True)
    quantity_on_hand = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    condition_grade = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='used_good')
    warehouse_location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_lots'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sku']

    @property
    def quantity_available(self):
        return max(self.quantity_on_hand - self.quantity_reserved, 0)

    def __str__(self):
        return f"{self.sku} - {self.product.name}"
    

class InventoryUnit(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
        ('donated', 'Donated'),
        ('disposed', 'Disposed'),
    ]

    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used_like_new', 'Used - Like New'),
        ('used_good', 'Used - Good'),
        ('used_fair', 'Used - Fair'),
        ('for_parts', 'For Parts / Not Working'),
        ('donate', 'Donate'),
        ('dispose', 'Dispose'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_units')
    sku = models.CharField(max_length=100, unique=True)
    serial_number = models.CharField(max_length=100, blank=True)
    condition_grade = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='used_good')
    warehouse_location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_units'
    )
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
        
    class Meta: 
        ordering = ['sku', 'id', 'condition_grade']

    def __str__(self) -> str:
        serial = self.serial_number or f"Unit {self.id}"
        return f"{self.sku} - {serial} - {self.condition_grade}"
        
        
class InventoryTransaction(models.Model):
    TRANSACTION_CHOICES = [
        ('receive', 'Receive'),
        ('adjust', 'Adjust'),
        ('reserve', 'Reserve'),
        ('release', 'Release'),
        ('sell', 'Sell'),
        ('return', 'Return'),
        ('damage', 'Damage'),
        ('transfer', 'Transfer'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_transactions')
    inventory_lot = models.ForeignKey(
        InventoryLot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transactions'
    )
    inventory_unit = models.ForeignKey(
        InventoryUnit,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_CHOICES)
    quantity_delta = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type} - {self.product.name} ({self.quantity_delta})"