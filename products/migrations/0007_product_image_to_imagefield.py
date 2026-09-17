"""URLField -> ImageField for Product.product_image.

Order matters: the old URL is copied into image_source_url first, then every
row is pointed at media/products/<slug>.jpg, and only then does the column
change type. Data migration runs before the AlterField so nothing is lost.
"""
from django.db import migrations, models


def copy_urls_and_point_at_files(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for p in Product.objects.all():
        old = p.product_image or ''
        if old.startswith('http'):
            p.image_source_url = old[:500]
        p.product_image = f'products/{p.slug}.jpg'
        p.save(update_fields=['product_image', 'image_source_url'])


def restore_urls(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for p in Product.objects.exclude(image_source_url=''):
        p.product_image = p.image_source_url[:200]
        p.save(update_fields=['product_image'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_drop_legacy_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='image_source_url',
            field=models.URLField(blank=True, default='', max_length=500, verbose_name='Original image URL'),
        ),
        migrations.RunPython(copy_urls_and_point_at_files, restore_urls),
        migrations.AlterField(
            model_name='product',
            name='product_image',
            field=models.ImageField(blank=True, max_length=200, null=True, upload_to='products/', verbose_name='Product Image'),
        ),
    ]
