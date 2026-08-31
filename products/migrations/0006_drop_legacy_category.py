
from django.db import migrations


def refuse_if_anything_is_uncategorised(apps, schema_editor):
    Product = apps.get_model('products', 'Product')

    orphans = [
        f'{p.id}: {p.name} (was "{p.legacy_category}")'
        for p in Product.objects.filter(categories__isnull=True)
    ]
    if orphans:
        raise RuntimeError(
            'These products have no category, and dropping legacy_category '
            'would lose the only record of what they are. Assign them in the '
            'admin, or extend the mapping in 0005, then migrate again:\n  '
            + '\n  '.join(orphans)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0005_seed_categories"),
    ]

    operations = [
        migrations.RunPython(
            refuse_if_anything_is_uncategorised,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="product",
            name="legacy_category",
        ),
    ]
