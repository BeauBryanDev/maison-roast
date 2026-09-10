
import re
import unicodedata

from django.conf import settings
from django.db.models import Q

from products.models import Category, Product

MAX_LIMIT = 25


def _serialize(product, full=False):
 
    categories = [c.name for c in product.categories.all()]
    alcohol = settings.ALCOHOL_CATEGORY_NAME.casefold()
    data = {
        'id': product.id,
        'name': product.name,
        'categories': categories,
        'price': str(product.price),
        'is_available': product.available and product.stock > 0,
        # Advisory only. The gate that counts is in orders.services.place_order.
        'is_alcohol': any(c.casefold() == alcohol for c in categories),
    }
    if full:
        data['description'] = product.description
        data['stock'] = product.stock
        data['slug'] = product.slug
        
    else:
        data['short_description'] = product.description[:120]
        
    return data


def search_menu(query=None, 
                category=None, 
                limit=10):
    
    try:
        limit = max(1, min(int(limit), MAX_LIMIT))
        
    except (TypeError, ValueError):
        limit = 10

    products = Product.objects.prefetch_related('categories')
    unmatched = None

    if category:
        
        exact = products.filter(categories__name__iexact=category)
        
        if exact.exists():
            products = exact
            
        else:
            # The model guessed a name we do not use ("drinks", "coffees").
            # A partial match beats reporting an empty menu; if that finds
            # nothing either, say which names are real rather than implying
            # the shop sells none of it.
            partial = products.filter(categories__name__icontains=category)
            
            if partial.exists():
                products = partial
                
            else:
                # Return nothing, not everything. Handing back the whole menu
                # would read as "these all match" -- a muffin as a drink.
                products = products.none()
                unmatched = category

    if query:
        matched = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
        if not matched.exists():
            # Same fold as check_product_availability: a CNN label or a typed
            # "creme brulee" must still find "Creme Brulee".
            matched = products.filter(
                pk__in=[p.pk for p in _fold_matches(products, query)]
            )
        products = matched

    results = [_serialize(p) for p in products.distinct().order_by('name')[:limit]]
    payload = {'count': len(results), 'results': results}

    if unmatched is not None:
        
        payload['note'] = (
            f'No category called "{unmatched}". Valid categories: '
            f'{", ".join(list_category_names())}.'
        )
    return payload


# List of category names that actually have a product behind them.
def list_category_names():
    """Category names that actually have a product behind them."""
    return list(
        Category.objects.filter(products__isnull=False)
        .distinct().order_by('name').values_list('name', flat=True)
    )

# Details for one product, by id.
def get_product_details(product_id):
    # ingredients and allergens are not on the model yet, so they are omitted
    # rather than returned empty.  
    try:
        product = Product.objects.prefetch_related('categories').get(pk=product_id)
        
    except (Product.DoesNotExist, ValueError, TypeError):
        return {'error': f'No product with id {product_id}.'}
    
    return _serialize(product, full=True)


def _fold(text):
    """Lowercase, strip accents, 
    drop everything that is not a letter or digit.
    """
    stripped = unicodedata.normalize('NFKD', str(text))
    # CNN  vision fields contain combining characters, which are not letters or digits.
    stripped = ''.join(c for c in stripped if not unicodedata.combining(c))
    
    return re.sub(r'[^a-z0-9]', '', stripped.lower())


# Products whose folded name matches 
def _fold_matches(catalog, text):
    """Products whose folded name matches `text`, exact matches first."""
    target = _fold(text)
    
    if not target:
        
        return []
    
    candidates = [(p, _fold(p.name)) for p in catalog]
    exact = [p for p, folded in candidates if folded == target]
    
    partial = [
        p for p, folded in candidates
        if folded != target and (target in folded or folded in target)
    ]
    return exact + partial



def _match_by_folded_name(catalog, product_name):
    
    matches = _fold_matches(catalog, product_name)
    
    return matches[0] if matches else None


def check_product_availability(product_id=None, product_name=None):
    
    catalog = Product.objects.prefetch_related('categories')

    if product_id is not None:
        product = catalog.filter(pk=product_id).first()
        
    elif product_name:
        product = catalog.filter(name__iexact=product_name).first()
        
        if product is None:
            product = catalog.filter(name__icontains=product_name).first()
            
        if product is None:
            product = _match_by_folded_name(catalog, product_name)
            
    else:
        return {'error': 'Provide product_id or product_name.'}

    if product is None:
        return {'exists': False, 'is_available': False}

    return {
        'exists': True,
        'is_available': product.available and product.stock > 0,
        'product': _serialize(product),
    }
