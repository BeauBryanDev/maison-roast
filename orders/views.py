from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import F
from django.views import View
from django.contrib import messages
from orders.models import Order, ProductOrder
from products.models import Product
from .forms import ProductOrderForm
import uuid
from datetime import datetime

# Create your views here.
class MyOrderList(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'
    
    def get_queryset(self):
        """Return orders for the current user that are active, newest first.

        Prefetches the line items because order_list.html now shows each order's
        item count and total (Order.total sums the lines). Without this the list
        costs a query per row.
        """
        return (
            Order.objects
            .filter(is_active=True, user=self.request.user)
            .prefetch_related('product_orders__product')
            .order_by('-created_at')
        )


class OrderDetail(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'
    pk_url_kwarg = 'pk'
    
    def get_queryset(self):
        """Limit detail view to active orders that belong to the requesting user."""
        # order_detail.html walks order.product_orders.all three times and reads
        # the product FK on every row, so without prefetching the page costs
        # one query per line item.
        return (
            Order.objects
            .filter(is_active=True, user=self.request.user)
            .prefetch_related('product_orders__product')
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class CreateOrderProductView(LoginRequiredMixin, View):
    """Handle buying a product - creates Order and ProductOrder"""

    def get(self, request):
        """Display the product order form"""
        # Get product ID from query parameter
        product_id = request.GET.get('product_id')

        if product_id:
            product = get_object_or_404(Product, id=product_id)

            # Pre-fill form with product data
            form = ProductOrderForm(initial={
                'product': product.id,
                'quantity': 1
            })

            return render(request, 'orders/product_order_form.html', {
                'product_order_form': form,
                'product': product
            })
        else:
            # No product specified
            form = ProductOrderForm()
            return render(request, 'orders/product_order_form.html', {
                'product_order_form': form
            })

    def post(self, request):
        """Handle the Buy Product button submission"""
        form = ProductOrderForm(request.POST)

        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            product = form.cleaned_data['product']
            product_id = product.pk

            # An order is a record we may need to act on -- a receipt, a refund,
            # a delivery question. Writing a placeholder address onto it would
            # make it look contactable when it is not, so refuse instead. This
            # is checked before the transaction so no row lock is taken for a
            # purchase that cannot proceed.
            if not request.user.email:
                messages.error(
                    request,
                    'Your account has no email address. Add one to your profile '
                    'before placing an order.'
                )
                return render(request, 'orders/product_order_form.html', {
                    'product_order_form': form,
                    'product': product
                })

            # The whole purchase is one transaction: either the order and the
            # stock decrement both land, or neither does.
            with transaction.atomic():
                # Re-fetch the product with a row lock held for the life of the
                # transaction. The copy the form loaded was read without a lock,
                # so it is not safe to check stock against -- a concurrent buyer
                # could pass the same check against the same units.
                product = Product.objects.select_for_update().get(pk=product_id)

                if not product.available:
                    messages.error(request, f'{product.name} is not currently available.')
                    return render(request, 'orders/product_order_form.html', {
                        'product_order_form': form,
                        'product': product
                    })

                # Check if product has enough stock
                if product.stock < quantity:
                    messages.error(request, f'Not enough stock! Only {product.stock} units available.')
                    return render(request, 'orders/product_order_form.html', {
                        'product_order_form': form,
                        'product': product
                    })

                # Generate unique order number
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                unique_id = str(uuid.uuid4())[:8].upper()
                order_number = f'ORD-{timestamp}-{unique_id}'

                # Get user information
                user = request.user
                customer_name = user.get_full_name() or user.username
                # Guaranteed non-empty by the check above.
                customer_email = user.email

                # Create the Order
                order = Order.objects.create(
                    user=user,
                    order_number=order_number,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    is_active=True
                )

                # Create the ProductOrder. Price always comes from the catalog
                # row, never from the request. It is stored on the line item so
                # the order keeps its historical price if the product is
                # repriced later.
                ProductOrder.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price_per_item=product.price
                )

                # Decrement stock in the database rather than in Python, so only
                # the stock column is written and the arithmetic cannot be lost.
                Product.objects.filter(pk=product.pk).update(stock=F('stock') - quantity)

            # Success message
            messages.success(
                request,
                f'Order #{order.order_number} created successfully! {quantity}x {product.name} added to your orders.'
            )

            # Redirect to My Orders
            return redirect('order_list')

        else:
            # Form is invalid - re-render with errors
            product_id = request.POST.get('product')
            product = None
            if product_id:
                try:
                    product = Product.objects.get(id=product_id)
                except Product.DoesNotExist:
                    pass

            return render(request, 'orders/product_order_form.html', {
                'product_order_form': form,
                'product': product
            })
    