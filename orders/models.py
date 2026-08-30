from decimal import Decimal

from django.db import models
from django.conf import settings

# Create your models here.

#create Order model to store order details
class Order(models.Model):
    
    # optional link to the authenticated user who placed the order
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders'
    )

    order_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def total(self):
        """Sum of the line items.

        Templates cannot sum across a loop -- the previous order detail page
        used {% widthratio %}, which returns an integer, so $2.99 x 2 rendered
        as "$6" instead of $5.98. Money arithmetic belongs here, in Decimal.

        Uses the prefetch cache when the queryset prefetched product_orders
        (OrderDetail.get_queryset does).
        """
        return sum(
            (line.subtotal for line in self.product_orders.all()),
            Decimal('0.00'),
        )

    def __str__(self) -> str:
        return f"Order {self.order_number} -{self.is_active} by {self.customer_name}" 
    

class ProductOrder(models.Model):
    
    order = models.ForeignKey(Order, related_name='product_orders', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_per_item = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def subtotal(self):
        """price_per_item * quantity, in Decimal -- never rounded for display."""
        return self.price_per_item * self.quantity

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product} for Order {self.order.order_number}"