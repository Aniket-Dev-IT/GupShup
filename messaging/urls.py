"""
URL Configuration for GupShup Messaging System
"""

from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Main messaging views
    path('', views.conversations_list_view, name='conversations'),
    path('new/', views.start_conversation_view, name='start_conversation'),
    path('new/<str:username>/', views.start_conversation_view, name='start_conversation_with_user'),
    path('<uuid:conversation_id>/', views.conversation_detail_view, name='conversation_detail'),
    
    # Profile integration
    path('profile/<str:username>/', views.message_from_profile_view, name='message_from_profile'),
    
    # AJAX endpoints
    path('api/send/<uuid:conversation_id>/', views.send_quick_message_ajax, name='send_quick_message'),
    path('api/poll/<uuid:conversation_id>/', views.get_new_messages_ajax, name='poll_messages'),
    path('api/conversation/<uuid:conversation_id>/action/', views.conversation_action_ajax, name='conversation_action'),
    path('api/message/<uuid:message_id>/delete/', views.delete_message_ajax, name='delete_message'),
    path('api/typing/<uuid:conversation_id>/', views.typing_indicator_ajax, name='typing_indicator'),
    
    # Additional features
    path('stats/', views.conversation_stats_view, name='stats'),
    path('api/search/', views.message_search_ajax, name='message_search'),
    path('api/conversation/<uuid:conversation_id>/settings/', views.conversation_settings_ajax, name='conversation_settings'),
    path('api/conversation/<uuid:conversation_id>/typing/', views.typing_status_ajax, name='typing_status'),
]