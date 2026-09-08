from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from orders.models import Order
from products.models import Product
from .forms import ProductOrderForm
from .services import OrderError, place_order

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
                f'Order #{order.order_number} created successfully! '
                f'{form.cleaned_data["quantity"]}x {product.name} added to your orders.'
            )
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

            return render(request, 
                          'orders/product_order_form.html', {
                            'product_order_form': form,
                            'product': product
            })
    