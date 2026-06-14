from decimal import Decimal
from django.db import models
from catalog.models import Product


class WarehouseLocation(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class InventoryLot(models.Model):
    LOT_TYPE_CHOICES = [
        ('manifested', 'Manifested'),
        ('unmanifested', 'Unmanifested'),
    ]

    STATUS_CHOICES = [
        ('pending_processing', 'Pending Processing'),
        ('active', 'Active'),
        ('closed', 'Closed'),
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

    # product is optional — unmanifested lots may contain mixed/unknown products
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='inventory_lots',
        null=True,
        blank=True,
    )
    sku = models.CharField(max_length=100, unique=True)
    lot_type = models.CharField(max_length=20, choices=LOT_TYPE_CHOICES, default='unmanifested')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_processing')
    supplier = models.CharField(max_length=255, blank=True)
    received_date = models.DateField(null=True, blank=True)

    # Cost tracking — unit_cost is derived: (purchase_cost + shipping_cost) / quantity_on_hand
    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    quantity_on_hand = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
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
        ordering = ['-created_at']

    @property
    def quantity_available(self):
        return max(self.quantity_on_hand - self.quantity_reserved, 0)

    @property
    def total_cost(self):
        return self.purchase_cost + self.shipping_cost

    @property
    def unit_cost(self):
        if self.quantity_on_hand:
            return self.total_cost / self.quantity_on_hand
        return Decimal('0')

    def __str__(self):
        label = self.product.name if self.product else "Mixed Lot"
        return f"{self.sku} - {label}"


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
    source_lot = models.ForeignKey(
        InventoryLot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='units'
    )
    sku = models.CharField(max_length=100, unique=True, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    condition_grade = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='used_good')
    warehouse_location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_units'
    )
    # Defaults to lot's derived unit_cost; can be overridden for high-value items
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    cost_overridden = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def _get_sku_prefix(self):
        """Walk category tree to find top-level category's sku_prefix."""
        cat = self.product.category if self.product else None
        while cat:
            if cat.sku_prefix:
                return cat.sku_prefix.upper()
            cat = cat.parent
        return 'GEN'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.sku:
            prefix = self._get_sku_prefix()
            lot_suffix = f"L{self.source_lot_id:04d}" if self.source_lot_id else "L0000"
            self.sku = f"{prefix}-{self.id:06d}-{lot_suffix}"
            super().save(update_fields=['sku'])

    def __str__(self):
        return f"{self.sku} - {self.product.name if self.product else 'Unknown'}"


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
