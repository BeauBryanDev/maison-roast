from django.urls import path
from .views import  MyOrderList , OrderDetail, CreateOrderProductView 

urlpatterns = [
    
    path('', MyOrderList.as_view(), name='order_list'),
    path('<int:pk>/', OrderDetail.as_view(), name='order_details'),
    path('add_product_order/', CreateOrderProductView.as_view(), name='add_product_order'),
]
