from django.db import models
from django.utils.text import slugify

# Create your models here.

class Product(models.Model):
    
    name = models.CharField(max_length=64 , verbose_name="Product Name") 
    description = models.TextField( max_length=255, verbose_name="Product Description")
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Product Price")
    stock = models.IntegerField()
    available = models.BooleanField(default=True)
    # Self-hosted since 2026-09-15: media/products/<slug>.jpg, 320x320, made by
    # `resize_product_images`. The URL each file was fetched from stays in
    # image_source_url so provenance is traceable.
    product_image = models.ImageField(upload_to='products/',
                                      max_length=200,
                                      null=True,
                                      blank=True,
                                      verbose_name="Product Image")
    image_source_url = models.URLField(max_length=500, blank=True, default='',
                                       verbose_name="Original image URL")
    slug = models.SlugField(max_length=64, unique=True, blank=True)
    # Many-to-many because one drink is honestly several things at once: an
    # Iced Latte is Coffee, Iced, Espresso and Milky. A single category would
    # make "show me hot coffee" miss whatever was filed under Latte.
    categories = models.ManyToManyField(
        'Category', related_name='products', blank=True,
        verbose_name="Product Categories",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            # slug is unique, so two products sharing a name would collide and
            # raise IntegrityError. Suffix a counter until the slug is free.
            base = slugify(self.name) or 'product'
            slug = base
            counter = 2
            
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                
                slug = f'{base}-{counter}'
                counter += 1
                
            self.slug = slug
            
        super().save(*args, **kwargs)

    def __str__(self):
        
        return f"{self.name} - ${self.price:.2f} - Stock: {self.stock}"
    
    
class Category(models.Model):
    
    name = models.CharField(max_length=32, unique=True, verbose_name="Category Name")
    description = models.TextField(max_length=255, blank=True, verbose_name="Category Description")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class ProductImage(models.Model):
    # TODO: add a product image path instead of a URL hotlink. 
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image_url = models.URLField(max_length=200, verbose_name="Image URL")
    alt_text = models.CharField(max_length=100, blank=True, verbose_name="Alt Text")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name} - {self.alt_text}"