"""
URL Configuration for GupShup Accounts App
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Home and main pages
    path('', views.home_view, name='home'),
    
    # Authentication URLs
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Profile URLs
    path('profile/complete/', views.ProfileCompletionView.as_view(), name='profile_completion'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    
    # Password Reset URLs
    path('password/reset/', views.password_reset_request, name='password_reset'),
    
    # AJAX URLs for real-time validation
    path('api/check-username/', views.check_username_availability, name='check_username'),
    path('api/check-email/', views.check_email_availability, name='check_email'),
    path('api/check-phone/', views.check_phone_availability, name='check_phone'),
]