"""
Views for GupShup Notification System
Handles notification display, management, and real-time updates
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.utils import timezone
import json

from .models import Notification, NotificationSetting
from accounts.models import GupShupUser


@login_required
def notifications_list_view(request):
    """
    Display paginated list of user notifications
    """
    # Get all notifications for the user
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('actor').order_by('-created_at')
    
    # Filter by type if specified
    notification_type = request.GET.get('type')
    if notification_type and notification_type != 'all':
        notifications = notifications.filter(notification_type=notification_type)
    
    # Filter by read status
    status_filter = request.GET.get('status')
    if status_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status_filter == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    notifications_page = paginator.get_page(page_number)
    
    # Get notification counts
    total_count = Notification.objects.filter(recipient=request.user).count()
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    
    context = {
        'notifications': notifications_page,
        'total_count': total_count,
        'unread_count': unread_count,
        'current_type': notification_type or 'all',
        'current_status': status_filter or 'all',
        'title': 'Notifications - GupShup'
    }
    
    return render(request, 'notifications/notifications_list.html', context)


@login_required
def notifications_ajax(request):
    """
    AJAX endpoint to get recent notifications for dropdown
    """
    # Get recent unread notifications
    recent_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).select_related('actor').order_by('-created_at')[:10]
    
    # Get total unread count
    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    # Format notifications for JSON response
    notifications_data = []
    for notification in recent_notifications:
        notifications_data.append({
            'id': str(notification.id),
            'title': notification.title,
            'message': notification.message[:100] + ('...' if len(notification.message) > 100 else ''),
            'actor_name': notification.get_actor_name(),
            'time_since': notification.get_time_since(),
            'icon': notification.get_icon(),
            'color_class': notification.get_color_class(),
            'action_url': notification.action_url,
            'notification_type': notification.notification_type,
        })
    
    return JsonResponse({
        'success': True,
        'notifications': notifications_data,
        'unread_count': unread_count,
        'has_notifications': len(notifications_data) > 0
    })


@login_required
@require_POST
def mark_notification_read_ajax(request, notification_id):
    """
    Mark a specific notification as read via AJAX
    """
    try:
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.mark_as_read()
        
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@require_POST
def mark_all_notifications_read_ajax(request):
    """
    Mark all notifications as read via AJAX
    """
    try:
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return JsonResponse({
            'success': True,
            'message': f'Marked {updated_count} notifications as read',
            'updated_count': updated_count
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@require_POST
def mark_notifications_read_bulk_ajax(request):
    """
    Mark multiple notifications as read via AJAX
    Compatible with both single IDs and bulk operations
    """
    try:
        data = json.loads(request.body)
        
        # Handle bulk mark all
        if data.get('mark_all', False):
            updated_count = Notification.objects.filter(
                recipient=request.user,
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
            
            return JsonResponse({
                'success': True,
                'message': f'Marked {updated_count} notifications as read',
                'updated_count': updated_count
            })
        
        # Handle specific notification IDs
        notification_ids = data.get('notification_ids', [])
        if not notification_ids:
            return JsonResponse({
                'success': False,
                'message': 'No notification IDs provided'
            })
        
        updated_count = Notification.objects.filter(
            id__in=notification_ids,
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return JsonResponse({
            'success': True,
            'message': f'Marked {updated_count} notifications as read',
            'updated_count': updated_count
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
def notification_settings_ajax(request):
    """
    Get or update notification settings via AJAX
    """
    try:
        # Get or create notification settings for user
        settings, created = NotificationSetting.objects.get_or_create(
            user=request.user,
            defaults={
                'email_on_like': True,
                'email_on_comment': True,
                'email_on_follow': True,
                'email_on_message': True,
                'push_on_message': True
            }
        )
        
        if request.method == 'POST':
            # Update settings
            data = json.loads(request.body)
            
            settings.email_on_like = data.get('email_likes', settings.email_on_like)
            settings.email_on_comment = data.get('email_comments', settings.email_on_comment)
            settings.email_on_follow = data.get('email_follows', settings.email_on_follow)
            settings.email_on_message = data.get('email_messages', settings.email_on_message)
            settings.push_on_message = data.get('push_enabled', settings.push_on_message)
            
            # Handle digest frequency (maps to auto cleanup)
            auto_cleanup = data.get('auto_cleanup', 'daily')
            if auto_cleanup == 'never':
                settings.digest_frequency = 'never'
            elif auto_cleanup in ['30', '60', '90']:
                settings.digest_frequency = 'daily'  # Map numeric values to daily for now
            else:
                settings.digest_frequency = auto_cleanup
            
            settings.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Settings updated successfully'
            })
        
        else:
            # Return current settings
            return JsonResponse({
                'success': True,
                'settings': {
                    'email_likes': settings.email_on_like,
                    'email_comments': settings.email_on_comment,
                    'email_follows': settings.email_on_follow,
                    'email_messages': settings.email_on_message,
                    'push_enabled': settings.push_on_message,
                    'auto_cleanup': settings.digest_frequency
                }
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
