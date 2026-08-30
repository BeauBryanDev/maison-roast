from django.contrib import admin
from .models import Order, ProductOrder


class ProductOrderInline(admin.TabularInline):
    """Line items, edited in place on the order they belong to."""

    model = ProductOrder
    extra = 0
    # Autocomplete keeps this usable once the catalog outgrows a plain <select>.
    autocomplete_fields = ['product']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer_name', 'customer_email', 'user',
                    'is_active', 'created_at', 'updated_at')
    search_fields = ('order_number', 'customer_name', 'customer_email')
    list_filter = ('is_active', 'created_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [ProductOrderInline]
    # created_at/updated_at are auto_now_add/auto_now: Django ignores any value
    # posted for them, so an editable widget would silently discard input.
    readonly_fields = ('created_at', 'updated_at')
    # The changelist shows order.user, which is a FK -- without this the list is
    # one extra query per row.
    list_select_related = ('user',)


@admin.register(ProductOrder)
class ProductOrderAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price_per_item')
    list_filter = ('order__is_active',)
    search_fields = ('order__order_number', 'product__name')
    autocomplete_fields = ['product']
    list_select_related = ('order', 'product')
