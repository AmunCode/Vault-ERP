from django.db import models
from decimal import Decimal
from catalog.models import Product
from inventory.models import InventoryUnit, InventoryLot

# Create your models here.
class Sale(models.Model):
    """Model representing a sale transaction for an inventory unit."""
    MARKETPLACE_CHOICES = [
        ('ebay', 'eBay'),
        ('whatnot', 'Whatnot'),
        ('poshmark', 'Poshmark'),
        ('walmart', 'Walmart'),
        ('amazon', 'Amazon'),
        ('facebook', 'Facebook Marketplace'),
        ('private_client', 'Private Client'),
        ('giveaway', 'Giveaway'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]

    sale_date = models.DateTimeField()
    marketplace = models.CharField(max_length=50, choices=MARKETPLACE_CHOICES)
    order_number = models.CharField(max_length=100, blank=True)
    customer_name = models.CharField(max_length=100, blank=True)
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    marketplace_fees = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    shipping_fees = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    special_fees = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    net_amount_received = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date']

    def __str__(self) -> str:
        ''' Return a string representation of the Sale instance, including the inventory unit, marketplace, sale price, and sale date.'''
        return f"{self.marketplace} - {self.order_number or self.id} - {self.status}"
    
class SaleLineItem(models.Model):
    """Model representing a line item within a sale, links a product to the sale transaction."""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sale_line_items')
    inventory_lot = models.ForeignKey(
        InventoryLot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_line_items'
    )
    inventory_unit = models.ForeignKey(
        InventoryUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_line_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    allocated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    

