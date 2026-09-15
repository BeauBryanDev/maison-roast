
from products.models import Product
 
from .menu import _fold
from basil.models import NutritionInfo 

# Nutrition lookup tool. Resolves a product (by id or name) to its
# NutritionInfo row by the same folding used in menu.py to match CNN labels
# against catalog names, it reused here because a customer might ask about a
# product name  that needs folding down to match the
# vision_label it was seeded under origina cnn classes .
 
def _resolve_search_text(product_id, product_name):
    """Return (text_to_fold, error_dict_or_None)."""
    if product_id is not None:
        
        try:
            product = Product.objects.get(pk=product_id)
            
        except (Product.DoesNotExist, ValueError, TypeError):
            return None, {'error': f'No product with id {product_id}.'}
        
        return product.name, None
 
    if product_name:
        return str(product_name), None
 
    return None, {'error': 'Provide product_id or product_name.'}
 
 
def _match_nutrition(text):
    """NutritionInfo row whose folded vision_label best matches folded text.
    """
    target = _fold(text)
    
    if not target:
        return None
 
    rows = list(NutritionInfo.objects.all())
    folded = [(row, _fold(row.vision_label)) for row in rows]
 
    for row, label in folded:
        
        if label == target:
            return row
 
    for row, label in folded:
        
        if label in target or target in label:
            return row
 
    return None
 
 
def get_nutrition_info(product_id=None, 
                       product_name=None):
    """Nutrition facts for a menu item, per basis_g grams (100g for all rows today)."""
    text, error = _resolve_search_text(product_id,
                                       product_name)
    
    if error:
        return error
 
    row = _match_nutrition(text)
    if row is None:
        return {
            'exists': False,
            'note': 'No nutrition data on file for that item.',
        }
 
    return {
        'exists': True,
        'vision_label': row.vision_label,
        'basis_g': row.basis_g,
        'calories_kcal': row.calories_kcal,
        'protein_g': row.protein_g,
        'carbs_g': row.carbs_g,
        'fat_g': row.fat_g,
        'note': f'Values are per {row.basis_g}g, not per serving.',
    }
 
 