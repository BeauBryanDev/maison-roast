from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

# Register your models here.

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 
                    'email', 
                    'first_name', 
                    'last_name', 
                    'phone_number', 
                    'date_of_birth', 
                    'is_staff', 
                    'is_active']
    
    list_filter = ['is_staff', 'is_active', 'is_superuser', 'gender']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    ordering = ['-date_joined']
    readonly_fields = ['date_joined', 'last_login']

    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info',
         {'fields': ('phone_number', 'address', 'gender', 'date_of_birth')}),
    )

 
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Personal Info', 
         {'fields': ('email', 'first_name', 'last_name')}),
        ('Additional Info',
         {'fields': ('phone_number', 'address')}),
        # NOT NULL with no default: without them here the add form 500s.
        ('Age Verification',
         {'fields': ('gender', 'date_of_birth')}),
    )
