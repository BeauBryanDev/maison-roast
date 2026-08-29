from django import forms
from django.forms import ModelForm
from .models import Order, ProductOrder

class OrderForm(ModelForm):
    class Meta:
        model = Order
        fields = ['order_number', 'customer_name', 'customer_email', 'is_active']
        
        
        
class ProductOrderForm(ModelForm):
    # price_per_item is deliberately NOT a form field. The price is read from
    # the Product row in the view, so it cannot be tampered with in the POST.
    class Meta:
        model = ProductOrder
        fields = ['product_name', 'quantity']

    def clean_quantity(self):
        # PositiveIntegerField permits 0, which would create an order for nothing.
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity < 1:
            raise forms.ValidationError("Quantity must be at least 1.")
        return quantity
