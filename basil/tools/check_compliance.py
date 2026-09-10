
from django.conf import settings
from django.utils import timezone

from orders.services import is_age_restricted, is_within_service_hours
from products.models import Product

# Alcohol compliance tool.

# Basil must call this before offering or ordering anything from the Alcohol
# category. Two conditions, both required: the caller is of legal drinking age,
# and the shop is past its alcohol service hour (evenings only).

def check_compliance(user, product_id=None):
    """Say whether alcohol may be sold to this caller right now."""
    minimum_age = settings.MINIMUM_ALCOHOL_AGE
    start_hour = settings.ALCOHOL_SERVICE_START_HOUR
    hour = timezone.localtime().hour

    if user is None or not getattr(user, 'is_authenticated', False):
        return {
            'may_sell_alcohol': False,
            'reason': 'not_signed_in',
            'message': 'Please sign in first — I cannot serve alcohol to a guest account.',
        }

    # Optional: confirm the product really is age-restricted before gating it.
    if product_id is not None:
        try:
            product = Product.objects.prefetch_related('categories').get(pk=product_id)
            
        except (Product.DoesNotExist, ValueError, TypeError):
            return {'error': f'No product with id {product_id}.'}
        
        if not is_age_restricted(product):
            return {
                'may_sell_alcohol': True,
                'reason': 'not_alcohol',
                'message': f'{product.name} is not an alcoholic item — no compliance check needed.',
            }

    age = getattr(user, 'age', None)
    of_age = bool(getattr(user, 'is_of_legal_age', None) and user.is_of_legal_age())
    # One definition, shared with the gate in place_order, so they cannot drift.
    in_hours = is_within_service_hours()

    result = {
        'user_age': age,
        'current_hour': hour,
        'minimum_age': minimum_age,
        'service_start_hour': start_hour,
    }

    if of_age and in_hours:
        result.update(
            may_sell_alcohol=True,
            reason='ok',
            message='Go ahead — this customer may be served alcohol.',
        )
        
    elif not of_age:
        result.update(
            may_sell_alcohol=False,
            reason='underage',
            message=(
                'Sorry, we cannot sell alcohol to minors. Offer something else '
                'from the menu instead.'
            ),
        )
        
    elif not in_hours:
        result.update(
            may_sell_alcohol=False,
            reason='before_service_hours',
            message=(
                f'Sorry, we do not sell alcohol before {start_hour}:00. '
                'Invite them back this evening.'
            ),
        )
        
    # unreachable, kept for clarity   
    else:
        result.update(
            may_sell_alcohol=False,
            reason='refused',
            message='Do not sell alcohol.',
        )
        
#    This tool exists so Basil can say no before
#    offering or ordering anything from the Alcohol category. 
       
    return result

