from django.urls import path, include
from . import views, api_views

app_name = 'admin_panel'

urlpatterns = [
    # Admin Dashboard (no login required - uses Django superuser check)
    path('', views.admin_dashboard_view, name='dashboard'),
    
    # Admin User Management
    path('users/', views.admin_users_view, name='user_list'), 
    path('users/<int:user_id>/', views.admin_user_detail_view, name='user_detail'),
    
    # Admin Analytics
    path('analytics/', views.admin_analytics_view, name='analytics'),
    
    # API endpoints
    path('api/', include([
        path('stats/dashboard/', api_views.DashboardStatsAPI.as_view(), name='api_dashboard_stats'),
        path('analytics/', api_views.AnalyticsAPI.as_view(), name='api_analytics'),
        path('users/search/', api_views.UserSearchAPI.as_view(), name='api_user_search'),
        path('users/<int:user_id>/detail/', api_views.UserDetailAPI.as_view(), name='api_user_detail'),
    ])),
]
