
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Category, Product
from .forms import ProductForm
from .serializers import ProductSerializer
from .permissions import IsStaffOrReadOnly

# Create your views here.

class HomeView(TemplateView):
    template_name = 'products/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
 
        context['featured_products'] = (
            Product.objects.filter(available=True).order_by('-created_at')[:5]
        )
        # Category tiles come from categories that actually have an available
        # product, so a tile can never lead to an empty menu page.
        context['categories'] = (
            Category.objects.filter(products__available=True)
            .distinct().order_by('name')
        )
        return context


class AboutView(TemplateView):
    template_name = 'products/about.html'


class BarView(ListView):
    # The evening menu. Matched on the category name, like every other filter
    # in this app, so the page keeps working if ids move.
    model = Product
    template_name = 'products/bar.html'
    context_object_name = 'products'
    BAR_CATEGORY = 'Alcohol'

    def get_queryset(self):
        return (
            Product.objects.filter(categories__name=self.BAR_CATEGORY)
            .prefetch_related('categories')
            .distinct().order_by('name')
        )


class FavouritesView(TemplateView):
    # Favourites live in the visitor's own localStorage, not the database, so
    # this renders a shell only. favourites.js reads the stored ids and fills
    # the grid from the public catalog API, which keeps prices and stock live
    template_name = 'products/favourites.html'
    # TOdO: add a "favourites" field to the user profile, so logged-in users can
    # keep their favourites across devices. The localStorage version is still
    # useful for anonymous visitors, and for logged-in users who don't want to log in just to browse the catalog.

class ProductListView(ListView):
    # The evening menu. Matched on the category name, like every other filter
    # in this app, so the page keeps working if ids move.
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 9  
    ordering = ['-created_at']

    def get_queryset(self):
        """Optionally narrow the menu with ?category=<name>.

        Unavailable products are deliberately NOT filtered out -- the templates
        show them with an "Out of Stock" badge and a disabled button, and the
        server refuses to sell them. See Refactor_backend.md #11.
        """
        queryset = super().get_queryset().prefetch_related('categories')
        category = self.request.GET.get('category')
        if category:
            # Matched on name so ?category=Coffee keeps working -- existing
            # links and the pagination URLs carry the name, not an id.
            queryset = queryset.filter(categories__name=category)
            
        return queryset

    def get_context_data(self, **kwargs):
        
        context = super().get_context_data(**kwargs)
        context['active_category'] = self.request.GET.get('category', '')
        context['categories'] = (
            Category.objects.filter(products__isnull=False)
            .distinct().order_by('name')
        )
        
        return context
    
class ProductDetailView(DetailView):
    
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        return context
    
    
class ProductFormView( LoginRequiredMixin, UserPassesTestMixin, CreateView ):

    # Adding to the catalog is a staff action [ admin / staff / superuser ].
    # the right thing here: anonymous visitors are redirected to the login page,
    # while authenticated non-staff users get a 403. Setting raise_exception
    # would give anonymous users a 403 too, with no way to log in.
    model = Product
    template_name = 'products/add_product.html'
    form_class = ProductForm
    success_url = reverse_lazy('product_list')

    def test_func(self):
        
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        
        context = super().get_context_data(**kwargs)
        
        return context


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
            return Response({'error': 'Product ID is required for update.'}, 
                            status=status.HTTP_400_BAD_REQUEST
                            )
        
        product = get_object_or_404(Product, pk=id)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        
        if serializer.is_valid():
            
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    def delete(self, request, format=None):
        
        id = request.query_params.get('id', None)
        
        if id is None:
            return Response(
                {'error': 'Product ID is required for deletion.'}, 
                status=status.HTTP_400_BAD_REQUEST
                )
        
        product = get_object_or_404(Product, pk=id)
        product.delete()
        
        return Response({'message': 'Product deleted successfully.'}, 
                        status=status.HTTP_200_OK
                        )
