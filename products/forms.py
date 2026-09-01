from django import forms
from .models import Product


# Products Forms
class ProductForm(forms.ModelForm):
    """
    Create/edit form for Product.

    A ModelForm rather than a plain Form: the field list, max_lengths and
    validation come from the model, so adding a model field no longer needs a
    matching edit here.
    """

    class Meta:
        model = Product
        fields = [
            'name',
            'description',
            'price',
            'stock',
            'available',
            'product_image',
            'categories',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'field-cream'}),
            'categories': forms.CheckboxSelectMultiple,
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        
        if price is not None and price < 0:
            
            raise forms.ValidationError("Price cannot be negative.")
        
        return price
