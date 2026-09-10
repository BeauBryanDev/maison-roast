
from orders.models import Order

MAX_LIMIT = 20

# Order history tool 

def read_orders(user, limit=5):
    
    if user is None or not user.is_authenticated:
        return {'error': 'Please sign in to see your orders.'}

    try:
        
        limit = max(1, min(int(limit), MAX_LIMIT))
        
    except (TypeError, ValueError):
        limit = 5

    # Same tenancy filter as MyOrderList.
    orders = (
        Order.objects
        .filter(user=user, is_active=True)
        .prefetch_related('product_orders__product')
        .order_by('-created_at')[:limit]
    )

    results = [{
        'order_number': o.order_number,
        'placed_at': o.created_at.isoformat(),
        'total': str(o.total),
        'items': [{
            'product': line.product.name,
            'quantity': line.quantity,
            'price_per_item': str(line.price_per_item),
            # currently  only one product per order
        } for line in o.product_orders.all()],
        
    } for o in orders]

    return {'count': len(results), 'orders': results}
