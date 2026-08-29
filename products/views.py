from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import  ListView, DetailView , TemplateView , FormView
from django.core.paginator import Paginator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Product
from .forms import ProductForm
from .serializers import ProductSerializer, CategorySerializer, ProductInCategorySerializer
from .permissions import IsStaffOrReadOnly
# Create your views here.

class home(TemplateView):
    template_name = 'products/home.html'
    

class ProductListView(ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 9  
    ordering = ['-created_at']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    
class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    
    
    
class ProductFormView( LoginRequiredMixin, UserPassesTestMixin, FormView ):

    # Adding to the catalog is a staff action. Django's AccessMixin already does
    # the right thing here: anonymous visitors are redirected to the login page,
    # while authenticated non-staff users get a 403. Setting raise_exception
    # would give anonymous users a 403 too, with no way to log in.
    template_name = 'products/add_product.html'
    form_class = ProductForm
    success_url = reverse_lazy('product_list')

    def test_func(self):
        return self.request.user.is_staff


    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
    
    

class ProductListAPI( APIView ):

    # Authentication falls back to the project default (SessionAuthentication).
    # Reads stay public; writes require a staff account.
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, format=None):
        
        id  = request.query_params.get('id', None)
        if id is not None:
            # get_object_or_404 raises Http404, which DRF renders as a clean 404.
            product = get_object_or_404(Product, pk=id)
            serializer = ProductSerializer(product)
            return Response(serializer.data, status=status.HTTP_200_OK)

        products = Product.objects.all().order_by('-created_at')
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, format=None):
        
        serializer = ProductSerializer(data=request.data)
        
        if serializer.is_valid():
            
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    def patch(self, request, format=None):
        
        id = request.data.get('id', None)
        
        if id is None:
            return Response({'error': 'Product ID is required for update.'}, status=status.HTTP_400_BAD_REQUEST)
        
        product = get_object_or_404(Product, pk=id)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    def delete(self, request, format=None):
        
        id = request.query_params.get('id', None)
        
        if id is None:
            return Response({'error': 'Product ID is required for deletion.'}, status=status.HTTP_400_BAD_REQUEST)
        
        product = get_object_or_404(Product, pk=id)
        product.delete()
        
        return Response({'message': 'Product deleted successfully.'}, status=status.HTTP_200_OK)
    
    
"""
mocha coffee adddress
https://hoxtoncoffee.com/cdn/shop/articles/latte-art-on-mocha_1200x1200.jpg?v=1660069726

Expreso Coffee address
https://www.cafe-mx.com/blog/app/assets/media/2018/08/cafe-expreso.jpg

capuchino coffee 
https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRfPhPty83awEZiMFjBwtr4qai6J1evVnn7Vg&s

cold brew 
https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQKPhK6VkiP1hWTryv_ZW_NvQsqAQ48VQRIug&s

Ice latte
https://markieskitchen.com/wp-content/uploads/2022/07/iced-mocha-latte-4.jpg

"""