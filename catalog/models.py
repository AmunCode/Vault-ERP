from django.db import models

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100)
    sku_prefix = models.CharField(max_length=3, blank=True, help_text="3-letter prefix for internal SKUs (top-level categories only, e.g. CLO, ELC)")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def __str__(self) -> str:
        return self.name

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    description = models.TextField(blank=True)
    upc = models.CharField(max_length=12, blank=True)
    hsn_item_number = models.CharField(max_length=10, blank=True, db_index=True)
    mpn = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name
