from django.urls import path
from .views import MyOrderList, OrderDetail, CreateOrderProductView, start_checkout
from .webhooks import stripe_webhook

urlpatterns = [
    path('', MyOrderList.as_view(), name='order_list'),
    path('<int:pk>/', OrderDetail.as_view(), name='order_details'),
    path('add_product_order/', CreateOrderProductView.as_view(), name='add_product_order'),
    path('checkout/<int:order_id>/', start_checkout, name='start_checkout'),
    path('stripe/webhook/', stripe_webhook, name='stripe_webhook'),
]
