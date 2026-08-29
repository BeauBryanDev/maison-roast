from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

# Register your models here.

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_active', 'is_superuser']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    ordering = ['-date_joined']
    readonly_fields = ['date_joined', 'last_login']

    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', 
         {'fields': ('phone_number', 'address')}),
    )

    # The stock add form collects only username and passwords. CustomUser.email
    # is unique and non-blank, so users added that way all get email='' and the
    # second one fails with an IntegrityError. Collect it up front, along with
    # the custom profile fields.
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Personal Info', 
         {'fields': ('email', 'first_name', 'last_name')}),
        ('Additional Info', 
         {'fields': ('phone_number', 'address')}),
    )
