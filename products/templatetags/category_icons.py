
from django import template
 
from products.category_icons import get_category_icon
 
register = template.Library()
 
# Usage: {{ category_name|category_icon }}

@register.filter
def category_icon(category_name):
    return get_category_icon(category_name)