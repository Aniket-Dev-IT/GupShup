"""
URL Configuration for GupShup Posts App
"""

from django.urls import path
from . import views

app_name = 'posts'

urlpatterns = [
    # Feed and main pages
    path('feed/', views.feed_view, name='feed'),
    path('explore/', views.explore_view, name='explore'),
    
    # Post CRUD operations
    path('create/', views.create_post_view, name='create'),
    path('<uuid:pk>/', views.post_detail_view, name='detail'),
    path('<uuid:pk>/edit/', views.edit_post_view, name='edit'),
    path('<uuid:pk>/delete/', views.delete_post_view, name='delete'),
    
    # Post interactions (AJAX)
    path('api/like/', views.like_post_view, name='like_post'),
    path('api/like-comment/', views.like_comment_view, name='like_comment'),
    path('api/delete-comment/', views.delete_comment_view, name='delete_comment'),
    
    # Hashtag and search features
    path('hashtag/<str:hashtag>/', views.hashtag_posts_view, name='hashtag_posts'),
    path('search/', views.search_posts_view, name='search'),
]