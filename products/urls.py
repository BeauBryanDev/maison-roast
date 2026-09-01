from django.urls import path
from . import views 
from .views import ProductListAPI

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    # Mounted at the root, not under products/, so it can never be shadowed by
    # the products/<slug> lookup below.
    path('favourites/', views.FavouritesView.as_view(), name='favourites'),
    path('bar/', views.BarView.as_view(), name='bar'),
    path('products/add/', views.ProductFormView.as_view(), name='product_add'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('api/products/', ProductListAPI.as_view(), name='product_list_api'),
    
]
