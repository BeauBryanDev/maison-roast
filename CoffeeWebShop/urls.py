"""
URL configuration for CoffeeWebShop project.

The `urlpatterns` list routes URLs to views. For
more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/

"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static


from orders.api import OrderDeleteAPIView
from users.api import ChangePasswordAPIView, MeAPIView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('products.urls')),
    path('users/', include('users.urls')),
    path('orders/', include('orders.urls')),
    path('basil/', include('basil.urls')),

    # Mounted here rather than in the app urlconfs so the paths are /api/...
    # and not /users/api/... 
    # users.urls is included under 'users/'.
    # The profile page drives these with fetch(); a browser <form> cannot send
    # PUT, PATCH or DELETE.
    path('api/users/me/', MeAPIView.as_view(), name='api_me'),
    path('api/users/me/password/', ChangePasswordAPIView.as_view(), name='api_me_password'),
    path('api/orders/<int:pk>/', OrderDeleteAPIView.as_view(), name='api_order_delete'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
