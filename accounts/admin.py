from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import GupShupUser


@admin.register(GupShupUser)
class GupShupUserAdmin(UserAdmin):
    """
    Custom admin for GupShup User with Indian-specific fields
    """
    
    # List display in admin
    list_display = [
        'username', 'email', 'get_display_name', 'phone_number',
        'city', 'state', 'is_verified', 'followers_count',
        'posts_count', 'is_active', 'date_joined'
    ]
    
    # Filters in admin
    list_filter = [
        'is_staff', 'is_superuser', 'is_active', 'is_verified',
        'preferred_language', 'state', 'date_joined', 'last_seen'
    ]
    
    # Search fields
    search_fields = [
        'username', 'first_name', 'last_name', 'email',
        'phone_number', 'city'
    ]
    
    # Fields layout in admin form
    fieldsets = UserAdmin.fieldsets + (
        (_('Indian Profile'), {
            'fields': (
                'phone_number', 'bio', 'city', 'state',
                'preferred_language', 'date_of_birth'
            )
        }),
        (_('Social Media'), {
            'fields': (
                'avatar', 'is_verified', 'is_private',
                'followers_count', 'following_count', 'posts_count'
            )
        }),
        (_('Activity'), {
            'fields': ('last_seen',),
            'classes': ('collapse',)
        })
    )
    
    # Add form fields
    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Indian Profile'), {
            'fields': (
                'phone_number', 'city', 'state', 'preferred_language'
            )
        }),
    )
    
    # Ordering
    ordering = ['-date_joined']
    
    # Read-only fields
    readonly_fields = UserAdmin.readonly_fields + (
        'last_seen', 'followers_count', 'following_count', 'posts_count'
    )
