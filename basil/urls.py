from django.urls import path

from . import views

urlpatterns = [
    path('chat/', views.chat, name='basil_chat'),
    path('history/', views.history, name='basil_history'),
    path('upload-image/', views.upload_image, name='basil_upload_image'),
]
