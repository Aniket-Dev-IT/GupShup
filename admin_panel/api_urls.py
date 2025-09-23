"""
GupShup Admin Panel API URLs

URL configuration for admin panel API endpoints and AJAX views.
"""

from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt

from .api_views import (
    # Dashboard APIs
    DashboardStatsAPI,
    AnalyticsAPI,
    
    # User Management APIs
    UserSearchAPI,
    UserDetailAPI,
    UserTimelineAPI,
    
    # Content Moderation APIs
    ModerationQueueAPI,
    
    # Bulk Operations APIs
    BulkActionsAPI,
    
    # Export APIs
    ExportDataAPI,
    
    # Real-time Updates API
    LiveUpdatesAPI,
    
    # Webhook
    automation_webhook,
)

app_name = 'admin_api'

urlpatterns = [
    
    # ================================
    # Dashboard and Statistics APIs
    # ================================
    
    path('dashboard/stats/', 
         DashboardStatsAPI.as_view(), 
         name='dashboard_stats'),
    
    path('analytics/', 
         AnalyticsAPI.as_view(), 
         name='analytics'),
    
    path('live-updates/', 
         LiveUpdatesAPI.as_view(), 
         name='live_updates'),
    
    # ================================
    # User Management APIs
    # ================================
    
    path('users/search/', 
         UserSearchAPI.as_view(), 
         name='user_search'),
    
    path('users/<int:user_id>/', 
         UserDetailAPI.as_view(), 
         name='user_detail'),
    
    path('users/<int:user_id>/timeline/', 
         UserTimelineAPI.as_view(), 
         name='user_timeline'),
    
    # ================================
    # Content Moderation APIs
    # ================================
    
    path('moderation/queue/', 
         ModerationQueueAPI.as_view(), 
         name='moderation_queue'),
    
    # ================================
    # Bulk Operations APIs
    # ================================
    
    path('bulk-actions/', 
         BulkActionsAPI.as_view(), 
         name='bulk_actions'),
    
    # ================================
    # Export APIs
    # ================================
    
    path('export/', 
         ExportDataAPI.as_view(), 
         name='export_data'),
    
    # ================================
    # Automation Webhook
    # ================================
    
    path('webhooks/automation/', 
         automation_webhook, 
         name='automation_webhook'),
]

# Additional API endpoint patterns for specific actions

# User Actions API patterns
user_action_patterns = [
    path('ban/', BulkActionsAPI.as_view(), {'action_type': 'ban'}, name='ban_user'),
    path('warn/', BulkActionsAPI.as_view(), {'action_type': 'warn'}, name='warn_user'),
    path('activate/', BulkActionsAPI.as_view(), {'action_type': 'activate'}, name='activate_user'),
    path('deactivate/', BulkActionsAPI.as_view(), {'action_type': 'deactivate'}, name='deactivate_user'),
]

# Content Actions API patterns
content_action_patterns = [
    path('approve/', ModerationQueueAPI.as_view(), {'action': 'approve'}, name='approve_content'),
    path('delete/', ModerationQueueAPI.as_view(), {'action': 'delete'}, name='delete_content'),
    path('flag/', ModerationQueueAPI.as_view(), {'action': 'flag'}, name='flag_content'),
    path('ignore/', ModerationQueueAPI.as_view(), {'action': 'ignore'}, name='ignore_content'),
]

# Analytics API patterns for specific types
analytics_patterns = [
    path('user-growth/', AnalyticsAPI.as_view(), {'type': 'user_growth'}, name='analytics_user_growth'),
    path('content-metrics/', AnalyticsAPI.as_view(), {'type': 'content_metrics'}, name='analytics_content_metrics'),
    path('geographic/', AnalyticsAPI.as_view(), {'type': 'geographic'}, name='analytics_geographic'),
    path('engagement/', AnalyticsAPI.as_view(), {'type': 'engagement'}, name='analytics_engagement'),
    path('hashtags/', AnalyticsAPI.as_view(), {'type': 'hashtags'}, name='analytics_hashtags'),
    path('viral/', AnalyticsAPI.as_view(), {'type': 'viral'}, name='analytics_viral'),
]

# Export API patterns for specific data types
export_patterns = [
    path('users/', ExportDataAPI.as_view(), {'type': 'users'}, name='export_users'),
    path('content/', ExportDataAPI.as_view(), {'type': 'content'}, name='export_content'),
    path('moderation/', ExportDataAPI.as_view(), {'type': 'moderation'}, name='export_moderation'),
    path('analytics/', ExportDataAPI.as_view(), {'type': 'analytics'}, name='export_analytics'),
]

# Add the nested patterns to main urlpatterns
urlpatterns += [
    path('users/actions/', include(user_action_patterns)),
    path('content/actions/', include(content_action_patterns)),
    path('analytics/', include(analytics_patterns)),
    path('export/', include(export_patterns)),
]