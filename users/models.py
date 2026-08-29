from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


# Create your models here.
class CustomUser(AbstractUser):
    """Custom User model extending AbstractUser"""
    
    username = models.CharField(_('username'), max_length=128, unique=True)
    first_name = models.CharField(_('first name'), max_length=32, blank=True)
    last_name = models.CharField(_('last name'), max_length=32, blank=True)
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(_('phone number'), max_length=16, blank=True, null=True)
    address = models.CharField(_('address'), max_length=255, blank=True)
    
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_groups',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )
    
    def __str__(self):
        
        return f"{self.username} - {self.email} - {self.first_name} {self.last_name}"