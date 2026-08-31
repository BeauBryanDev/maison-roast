"""
build the category set and assign every product to it.

The old free-text values overlapped -- Hot Coffee, Espresso, Latte and Milky
all described the same drinks, and only one could be chosen per product. The
new set is layered instead: what it is (Coffee, Non-Coffee, Pastry, Dessert),
how it is served (Hot, Iced), and what style it is (Espresso, Milky).

Two products are also corrected here, both approved:
  - Dark Coffee was filed under Pastry.
  - Americano Coffeee and Maccachiato were misspelled.
"""

from django.db import migrations
from django.utils.text import slugify

CATEGORIES = [
    ('Coffee', 'Anything made with coffee.'),
    ('Non-Coffee', 'Drinks with no coffee in them.'),
    ('Hot', 'Served hot.'),
    ('Iced', 'Served cold or over ice.'),
    ('Espresso', 'Built on espresso shots.'),
    ('Milky', 'Milk-forward drinks.'),
    ('Pastry', 'Baked goods from the case.'),
    ('Dessert', 'Cakes, tarts and sweets.'),
    ('Alcohol', 'Contains alcohol. Never suggest this unprompted.'),
]

# Keyed on the product name as it stands before the spelling fixes below.
ASSIGNMENTS = {
    'Espresso': ['Coffee', 'Hot', 'Espresso'],
    'Cappuccino': ['Coffee', 'Hot', 'Espresso', 'Milky'],
    'Mocha': ['Coffee', 'Hot', 'Espresso', 'Milky'],
    'Americano Coffeee': ['Coffee', 'Hot', 'Espresso'],
    'Maccachiato': ['Coffee', 'Hot', 'Espresso', 'Milky'],
    'Dark Coffee': ['Coffee', 'Hot'],
    'Iced Latte': ['Coffee', 'Iced', 'Espresso', 'Milky'],
    'Cold Brew': ['Coffee', 'Iced'],
    'Strawberry Milk Drink': ['Non-Coffee', 'Milky'],
    'Vanilla Milkshake': ['Non-Coffee', 'Milky', 'Iced'],
    'Cabernet Sauvignon Red Wine': ['Non-Coffee', 'Alcohol'],
    'Blueberry Muffin': ['Pastry'],
    'Classic Apple Pie': ['Dessert'],
    'New York Cheesecake': ['Dessert'],
}

RENAMES = {
    'Americano Coffeee': 'Americano Coffee',
    'Maccachiato': 'Macchiato',
}

# Anything not named above, and any product added between writing and running
# this, falls back to its old free-text value.
FALLBACK = {
    'Hot Coffee': ['Coffee', 'Hot'],
    'Cold Coffee': ['Coffee', 'Iced'],
    'Espresso': ['Coffee', 'Hot', 'Espresso'],
    'Latte': ['Coffee', 'Hot', 'Espresso', 'Milky'],
    'Milky': ['Milky'],
    'Beverage': ['Non-Coffee'],
    'Pastry': ['Pastry'],
    'Dessert': ['Dessert'],
}


def seed(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    Product = apps.get_model('products', 'Product')

    lookup = {}
    for name, description in CATEGORIES:
        category, _ = Category.objects.get_or_create(
            name=name, defaults={'description': description})
        lookup[name] = category

    for product in Product.objects.all():
        names = ASSIGNMENTS.get(product.name)
        if names is None:
            names = FALLBACK.get(product.legacy_category, [])

        product.categories.set([lookup[n] for n in names if n in lookup])

        new_name = RENAMES.get(product.name)
        if new_name:
            # The slug is generated once by Product.save() and never revisited,
            # so a corrected name leaves a misspelled URL behind. Orders point
            # at the product by id, so changing it breaks nothing.
            product.name = new_name
            product.slug = slugify(new_name)
            product.save(update_fields=['name', 'slug'])


def unseed(apps, schema_editor):
    """Reversible: drop the links and the categories this migration created.

    The spelling fixes are not undone -- reverting a migration should not put
    a typo back into the catalog.
    """
    Category = apps.get_model('products', 'Category')
    Product = apps.get_model('products', 'Product')

    for product in Product.objects.all():
        product.categories.clear()
    Category.objects.filter(name__in=[name for name, _ in CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_add_product_categories"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
