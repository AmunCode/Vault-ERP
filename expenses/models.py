from django.db import models
from decimal import Decimal
from catalog.models import Product
from inventory.models import InventoryLot, InventoryUnit
from sales.models import Sale

# Create your models here.
class ExpenseCategory(models.Model):
    """Model representing a category for expenses related to sales, such as shipping or marketplace fees."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Expense categories'

    def __str__(self):
        return self.name


class Expense(models.Model):
    MARKETPLACE_CHOICES = [
        ('ebay', 'eBay'),
        ('whatnot', 'Whatnot'),
        ('poshmark', 'Poshmark'),
        ('walmart', 'Walmart'),
        ('amazon', 'Amazon'),
        ('facebook', 'Facebook Marketplace'),
        ('private_client', 'Private Client'),
        ('other', 'Other'),
    ]

    expense_date = models.DateField()
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    vendor = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    marketplace = models.CharField(max_length=50, choices=MARKETPLACE_CHOICES, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    inventory_lot = models.ForeignKey(
        InventoryLot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    inventory_unit = models.ForeignKey(
        InventoryUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    is_recurring = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.category.name} - {self.amount}"