
from django.urls import reverse

from orders.services import OrderError, place_order

# Order placement tool  

# Delegates to orders.services.place_order so the checkout invariants are
# enforced. The caller is responsible for the user identity and the quantity.

def create_order(user, product_id, quantity=1, customer_notes=None):
    if user is None or not user.is_authenticated:
        return {
            'error': 'Please sign in to place an order.',
            'login_url': reverse('login'),
        }

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return {'error': 'Quantity must be a whole number.'}

    try:
        order = place_order(user=user, product_id=product_id, quantity=quantity)
    except OrderError as exc:
        return {'error': str(exc)}

    return {
        'order_id': order.id,
        'order_number': order.order_number,
        'status': 'pending',
        'total': str(order.total),
        'checkout_url': reverse('order_details', args=[order.pk]),
    }
