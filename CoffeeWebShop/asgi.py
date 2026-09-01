"""
ASGI config for CoffeeWebShop project.

"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoffeeWebShop.settings')

application = get_asgi_application()
