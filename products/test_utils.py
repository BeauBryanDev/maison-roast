"""
Shared test helper. Categories are an M2M, so they cannot be passed to
Product.objects.create() -- the rows need a pk first.
"""

from .models import Category, Product


def make_product(*categories, **fields):
    
    product = Product.objects.create(**fields)
    
    if categories:
        
        product.categories.set([
            Category.objects.get_or_create(name=name)[0] for name in categories
        ])
        
    return product
