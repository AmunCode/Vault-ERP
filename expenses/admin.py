from django.contrib import admin
from .models import ExpenseCategory, Expense

# Register your models here.
@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_date', 'category', 'amount', 'vendor', 'marketplace', 'is_recurring')
    search_fields = ('vendor', 'reference_number', 'description')
    list_filter = ('category', 'marketplace', 'is_recurring', 'expense_date')