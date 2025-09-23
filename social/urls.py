"""
URL Configuration for GupShup Social Features
"""

from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # User search and discovery
    path('discover/', views.discover_users_view, name='discover'),
    path('search/', views.user_search_view, name='user_search'),
    path('suggested/', views.suggested_users_view, name='suggested_users'),
    
    # User profiles
    path('u/<str:username>/', views.user_profile_view, name='profile'),
    path('u/<str:username>/followers/', views.followers_list_view, name='followers'),
    path('u/<str:username>/following/', views.following_list_view, name='following'),
    
    
    # Follow actions (AJAX)
    path('follow/<str:username>/', views.follow_action_view, name='follow_action'),
]