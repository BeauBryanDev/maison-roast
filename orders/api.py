from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product

from .models import Order


class OrderDeleteAPIView(APIView):
    """
    DELETE /api/orders/<pk>/ -- the customer regrets the purchase.

    Soft delete: is_active=False, using the flag the project already treats as
    the visibility/soft-delete marker. MyOrderList and OrderDetail both filter
    is_active=True, so the order disappears from the customer's side while the
    shop keeps the sales record for traceability.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        with transaction.atomic():
            # Scoped to the requesting user (tenancy) and to still-active orders,
            # so a second DELETE is a 404 rather than a second stock restore.
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=pk,
                user=request.user,
                is_active=True,
            )

            # Give the units back. This is the exact inverse of the decrement in
            # CreateOrderProductView and carries the same race, so it is an F()
            # update inside the same transaction.
            for line in order.product_orders.all():
                
                Product.objects.filter(pk=line.product_id).update(
                    stock=F('stock') + line.quantity
                )

            order.is_active = False
            order.save(update_fields=['is_active'])

        return Response(status=status.HTTP_204_NO_CONTENT)
