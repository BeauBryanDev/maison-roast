
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_category_productimage"),
    ]

    operations = [
        migrations.RenameField(
            model_name="product",
            old_name="category",
            new_name="legacy_category",
        ),
        migrations.AlterField(
            model_name="product",
            name="legacy_category",
            field=models.CharField(
                blank=True, max_length=32, verbose_name="Product Category (legacy)"
            ),
        ),
    ]
