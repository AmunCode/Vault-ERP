from django import forms
from .models import InventoryLot, InventoryUnit, WarehouseLocation


class LotReceiveForm(forms.ModelForm):
    class Meta:
        model = InventoryLot
        fields = [
            'sku', 'lot_type', 'supplier', 'received_date',
            'quantity_on_hand', 'purchase_cost', 'shipping_cost',
            'condition_grade', 'warehouse_location', 'notes',
        ]
        widgets = {
            'received_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput,
                                         forms.Select, forms.DateInput, forms.Textarea)):
                field.widget.attrs.setdefault('class', 'form-control')
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
        self.fields['warehouse_location'].queryset = WarehouseLocation.objects.filter(is_active=True)
        self.fields['warehouse_location'].required = False


class UnitProcessForm(forms.ModelForm):
    class Meta:
        model = InventoryUnit
        fields = [
            'condition_grade', 'size', 'color', 'qty', 'unit_cost', 'cost_overridden',
            'serial_number', 'warehouse_location', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'qty': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput,
                                         forms.Select, forms.Textarea)):
                field.widget.attrs.setdefault('class', 'form-control')
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
        self.fields['warehouse_location'].queryset = WarehouseLocation.objects.filter(is_active=True)
        self.fields['warehouse_location'].required = False
        self.fields['cost_overridden'].widget = forms.HiddenInput()
