"""
URL configuration for GupShup project.

Built with love in India 🇮🇳
A unique social platform connecting Indians worldwide
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Custom admin site headers
admin.site.site_header = "GupShup Admin"
admin.site.site_title = "GupShup Admin Portal"
admin.site.index_title = "Welcome to GupShup Administration"

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Main app URLs
    path('', include('accounts.urls')),
    
    # App URLs
    path('posts/', include('posts.urls')),
    path('social/', include('social.urls')),
    path('messages/', include('messaging.urls')),
    path('notifications/', include('notifications.urls')),
    path('', include('pages.urls')),
    
    # GupShup Admin Panel URLs (modern UI)
    path('admin-panel/', include('admin_panel.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
