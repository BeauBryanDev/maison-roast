
import stripe

from django.conf import settings

from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from orders.models import Order, Status
from products.models import Product
from .forms import ProductOrderForm
from .services import OrderError, place_order

# Connect to Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

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
            .prefetch_related('product_orders__product__categories')
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
            .prefetch_related('product_orders__product__categories')
        )
    
    def get(self, request, *args, **kwargs):
        # Stripe sends the browser back here with ?checkout=success|cancelled.
        # Success only means the customer finished the hosted page; the badge
        # turns Paid when the webhook says so.
        flag = request.GET.get('checkout')
        if flag == 'success':
            messages.success(request, 'Thank you! Your payment is being confirmed.')
        elif flag == 'cancelled':
            messages.warning(request, 'Payment cancelled. Your order is still awaiting payment.')
        return super().get(request, *args, **kwargs)


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
            product = form.cleaned_data['product']

            try:
                order = place_order(
                    user=request.user,
                    product_id=product.pk,
                    quantity=form.cleaned_data['quantity'],
                )
            except OrderError as exc:
                messages.error(request, str(exc))
                
                return render(request, 'orders/product_order_form.html', {
                    'product_order_form': form,
                    'product': product,
                })

            messages.success(
                request,
                f'Order #{order.order_number} created: '
                f'{form.cleaned_data["quantity"]}x {product.name}. Pay below to confirm it.'
            )
            # Land on the order itself, where the Pay button is.
            return redirect('order_details', pk=order.pk)

        else:
            # Form is invalid - re-render with errors
            product_id = request.POST.get('product')
            product = None
            
            if product_id:
                
                try:
                    product = Product.objects.get(id=product_id)
                    
                except Product.DoesNotExist:
                    pass

            return render(request, 
                          'orders/product_order_form.html', {
                            'product_order_form': form,
                            'product': product
            })
    
    
# Stripe Checkout is fully hosted, so this view's only job is to create the
# Session and bounce the browser to its url. Payment sits *after* place_order
# on purpose: the Order and its stock reservation already exist, so no database
# lock is held across the network call to Stripe, and place_order stays the one
# audited path. The webhook (orders/webhooks.py) flips the order to PAID; the
# success_url is only where the browser lands, never proof of payment.

@login_required
@require_POST
def start_checkout(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user, is_active=True)

    if order.status != Status.PENDING:
        messages.info(request, 'This order is not awaiting payment.')
        return redirect('order_details', pk=order.pk)

    # Single line item: this backend only ever creates one ProductOrder per
    # Order (quantity can be >1 of the same product, never a second product).
    line = order.product_orders.select_related('product').get()
    detail_url = request.build_absolute_uri(reverse('order_details', args=[order.pk]))

    try:
        session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(line.price_per_item * 100),  # Stripe wants cents
                    'product_data': {'name': line.product.name},
                },
                'quantity': line.quantity,
            }],
            customer_email=order.customer_email,
            client_reference_id=str(order.pk),
            success_url=detail_url + '?checkout=success',
            cancel_url=detail_url + '?checkout=cancelled',
            metadata={'order_id': str(order.pk), 'order_number': order.order_number},
        )
    except stripe.error.StripeError:
        messages.error(request, 'We could not reach our payment provider. Please try again.')
        return redirect('order_details', pk=order.pk)

    order.stripe_checkout_session_id = session.id
    order.save(update_fields=['stripe_checkout_session_id'])

    return redirect(session.url, permanent=False)
