from django.contrib import admin
from .models import Category, Product

# Register your models here.

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_list', 'price', 'stock', 'available', 'created_at']
    list_filter = ['available', 'categories', 'created_at']
    list_editable = ['price', 'stock', 'available']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['categories']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    # auto_now_add / auto_now: any posted value is discarded, so don't offer a widget.
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        # category_list reads the M2M on every row; without this the changelist
        # costs a query per product.
        return super().get_queryset(request).prefetch_related('categories')

    @admin.display(description='Categories')
    def category_list(self, product):
        return ', '.join(c.name for c in product.categories.all()) or '--'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count', 'description']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description='Products')
    def product_count(self, category):
        return category.products.count()
