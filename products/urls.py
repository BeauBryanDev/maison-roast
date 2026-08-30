from django.urls import path
from . import views 
from .views import ProductListAPI

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/add/', views.ProductFormView.as_view(), name='product_add'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('api/products/', ProductListAPI.as_view(), name='product_list_api'),
    
]
