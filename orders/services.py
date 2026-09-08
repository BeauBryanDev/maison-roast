
import uuid
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import F

from products.models import Product

from .models import Order, ProductOrder


class OrderError(Exception):
    """Purchase refused for a reason the caller should show the user."""


def is_age_restricted(product):
    """True if the product carries the alcohol category."""
    return product.categories.filter(
        name__iexact=settings.ALCOHOL_CATEGORY_NAME
    ).exists()


def generate_order_number():
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f'ORD-{stamp}-{str(uuid.uuid4())[:8].upper()}'


def place_order(user, product_id, quantity):
    """Create an order for one product. Returns the Order.

    Raises OrderError with a user-facing message if the purchase is refused.
    """
    if quantity is None or quantity < 1:
        raise OrderError('Quantity must be at least 1.')

    # An order we cannot contact is worse than no order, so refuse rather than
    # writing a placeholder address.
    if not user.email:
        raise OrderError(
            'Your account has no email address. Add one to your profile '
            'before placing an order.'
        )

    with transaction.atomic():
        # Locked re-fetch: the caller's copy was read without a lock, so it is
        # not safe to check stock against.
        try:
            product = Product.objects.select_for_update().get(pk=product_id)
            
        except Product.DoesNotExist:
            raise OrderError('That product does not exist.')

        if not product.available:
            raise OrderError(f'{product.name} is not currently available.')

        # Age gate. Here, not in the view or the prompt: this is the one path
        # both the web checkout and Basil's create_order tool go through, so
        # neither can bypass it. Runs before stock is touched.
        if is_age_restricted(product) and not (
            getattr(user, 'is_of_legal_age', None) and user.is_of_legal_age()
        ):
            raise OrderError(
                f'We cannot sell alcohol to anyone under '
                f'{settings.MINIMUM_ALCOHOL_AGE}. Please choose something else '
                f'from the menu.'
            )

        if product.stock < quantity:
            raise OrderError(
                f'Not enough stock! Only {product.stock} units available.'
            )

        order = Order.objects.create(
            user=user,
            order_number=generate_order_number(),
            customer_name=user.get_full_name() or user.username,
            customer_email=user.email,
            is_active=True,
        )

        # Price comes from the catalog row, never from the caller.
        ProductOrder.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price_per_item=product.price,
        )

        Product.objects.filter(pk=product.pk).update(stock=F('stock') - quantity)

    return order
