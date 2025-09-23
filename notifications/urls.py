"""
URL Configuration for GupShup Notifications System
"""

from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Main notification views
    path('', views.notifications_list_view, name='list'),
    
    # AJAX endpoints for real-time updates
    path('ajax/', views.notifications_ajax, name='ajax'),
    path('ajax/read/<uuid:notification_id>/', views.mark_notification_read_ajax, name='mark_read_single'),
    path('ajax/read-all/', views.mark_all_notifications_read_ajax, name='mark_all_read'),
    
    # API endpoints for compatibility
    path('api/mark-read/', views.mark_notifications_read_bulk_ajax, name='mark_read_bulk'),
    path('api/settings/', views.notification_settings_ajax, name='settings'),
]
