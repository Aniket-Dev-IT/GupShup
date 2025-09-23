"""
Views for GupShup Messaging System
Handles conversation management, message sending, and real-time chat functionality
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Max
from django.views.decorators.http import require_POST, require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from django.urls import reverse_lazy
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta

from .models import Conversation, Message
from .forms import MessageForm, QuickMessageForm, ConversationSearchForm, StartConversationForm
from accounts.models import GupShupUser
from notifications.models import Notification
from social.models import Follow


@login_required
def conversations_list_view(request):
    """
    Display list of user's conversations with search functionality
    """
    search_form = ConversationSearchForm(request.GET or None)
    conversations = []
    
    if search_form.is_valid():
        conversations = search_form.search_conversations(request.user)
    else:
        conversations = Conversation.get_user_conversations(request.user)
    
    # Add unread message counts and last message for each conversation
    conversation_data = []
    for conversation in conversations[:20]:  # Limit to 20 recent conversations
        other_user = conversation.get_other_user(request.user)
        last_message = conversation.get_last_message()
        unread_count = conversation.get_unread_count(request.user)
        
        conversation_data.append({
            'conversation': conversation,
            'other_user': other_user,
            'last_message': last_message,
            'unread_count': unread_count,
            'is_blocked': conversation.is_blocked
        })
    
    context = {
        'conversation_data': conversation_data,
        'search_form': search_form,
        'total_unread': sum(conv['unread_count'] for conv in conversation_data),
        'title': 'Messages - GupShup'
    }
    
    return render(request, 'messaging/conversations_list.html', context)


@login_required
def conversation_detail_view(request, conversation_id):
    """
    Display conversation thread with messages and send message form
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Check if user is participant
    if not conversation.is_participant(request.user):
        raise Http404("Conversation not found")
    
    # Check if conversation is blocked
    if conversation.is_blocked and conversation.blocked_by != request.user:
        messages.error(request, "This conversation has been blocked.")
        return redirect('messaging:conversations')
    
    # Get other user
    other_user = conversation.get_other_user(request.user)
    
    # Mark messages as read
    conversation.mark_messages_read(request.user)
    
    # Get messages with pagination
    messages_list = Message.objects.filter(
        conversation=conversation,
        is_deleted=False
    ).select_related('sender').order_by('sent_at')
    
    paginator = Paginator(messages_list, 50)
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    # Handle message form submission
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            
            # Set message type based on content
            if message.image:
                message.message_type = 'image'
            elif message.file:
                message.message_type = 'file'
            else:
                message.message_type = 'text'
            
            message.save()
            
            # Create notification for other user
            if other_user != request.user:
                Notification.create_message_notification(
                    sender=request.user,
                    recipient=other_user,
                    conversation=conversation
                )
            
            messages.success(request, "Message sent!")
            return redirect('messaging:conversation_detail', conversation_id=conversation.id)
    else:
        form = MessageForm()
    
    # Check if users can message each other (privacy check)
    can_message = True
    if other_user != request.user:
        # Check if other user has private account and current user is not following
        if other_user.is_private:
            is_following = Follow.objects.filter(
                follower=request.user,
                following=other_user,
                status='accepted'
            ).exists()
            if not is_following:
                can_message = False
    
    context = {
        'conversation': conversation,
        'other_user': other_user,
        'messages': messages_page,
        'form': form,
        'can_message': can_message,
        'is_blocked': conversation.is_blocked,
        'blocked_by_me': conversation.blocked_by == request.user if conversation.is_blocked else False,
        'title': f'Chat with {other_user.get_display_name()}'
    }
    
    return render(request, 'messaging/conversation_detail.html', context)


@login_required
def start_conversation_view(request, username=None):
    """
    Start a new conversation with a user
    """
    if request.method == 'POST':
        form = StartConversationForm(request.POST)
        if form.is_valid():
            target_user = form.get_target_user()
            
            if target_user == request.user:
                messages.error(request, "You cannot message yourself!")
                return redirect('messaging:start_conversation')
            
            # Get or create conversation
            conversation, created = Conversation.get_or_create_conversation(
                request.user, target_user
            )
            
            # Send initial message if provided
            initial_message = form.cleaned_data.get('message', '').strip()
            if initial_message:
                message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    content=initial_message,
                    message_type='text'
                )
                
                # Create notification
                Notification.create_message_notification(
                    sender=request.user,
                    recipient=target_user,
                    conversation=conversation
                )
            
            if created:
                messages.success(request, f"Started conversation with {target_user.get_display_name()}!")
            
            return redirect('messaging:conversation_detail', conversation_id=conversation.id)
    else:
        # Pre-fill username if provided
        initial_data = {'username': username} if username else {}
        form = StartConversationForm(initial=initial_data)
    
    context = {
        'form': form,
        'username': username,
        'title': 'Start New Conversation'
    }
    
    return render(request, 'messaging/start_conversation.html', context)


@login_required
@require_POST
def send_quick_message_ajax(request, conversation_id):
    """
    AJAX endpoint for sending quick messages
    """
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        # Check permissions
        if not conversation.is_participant(request.user):
            return JsonResponse({'success': False, 'message': 'Permission denied'})
        
        if conversation.is_blocked and conversation.blocked_by != request.user:
            return JsonResponse({'success': False, 'message': 'Conversation is blocked'})
        
        # Parse JSON data
        data = json.loads(request.body)
        form = QuickMessageForm(data)
        
        if form.is_valid():
            content = form.cleaned_data['content']
            
            # Create message
            message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content,
                message_type='text'
            )
            
            # Create notification
            other_user = conversation.get_other_user(request.user)
            Notification.create_message_notification(
                sender=request.user,
                recipient=other_user,
                conversation=conversation
            )
            
            # Return message data
            return JsonResponse({
                'success': True,
                'message': {
                    'id': str(message.id),
                    'content': message.content,
                    'sender_name': message.sender.get_display_name(),
                    'sent_at': message.sent_at.strftime('%H:%M'),
                    'is_own_message': True
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid message content',
                'errors': form.errors
            })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def message_from_profile_view(request, username):
    """
    Start conversation from user profile
    """
    target_user = get_object_or_404(GupShupUser, username=username, is_active=True)
    
    if target_user == request.user:
        messages.error(request, "You cannot message yourself!")
        return redirect('social:profile', username=username)
    
    # Get or create conversation
    conversation, created = Conversation.get_or_create_conversation(
        request.user, target_user
    )
    
    if created:
        messages.success(request, f"Started conversation with {target_user.get_display_name()}!")
    
    return redirect('messaging:conversation_detail', conversation_id=conversation.id)


@login_required
@require_POST
def conversation_action_ajax(request, conversation_id):
    """
    AJAX endpoint for conversation actions (block, unblock, delete)
    """
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        if not conversation.is_participant(request.user):
            return JsonResponse({'success': False, 'message': 'Permission denied'})
        
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'block':
            conversation.is_blocked = True
            conversation.blocked_by = request.user
            conversation.save()
            return JsonResponse({'success': True, 'message': 'User blocked'})
        
        elif action == 'unblock':
            if conversation.blocked_by == request.user:
                conversation.is_blocked = False
                conversation.blocked_by = None
                conversation.save()
                return JsonResponse({'success': True, 'message': 'User unblocked'})
            else:
                return JsonResponse({'success': False, 'message': 'You cannot unblock this conversation'})
        
        elif action == 'delete':
            # Soft delete - mark as inactive for this user
            conversation.is_active = False
            conversation.save()
            return JsonResponse({'success': True, 'message': 'Conversation deleted'})
        
        elif action == 'clear':
            # Mark all messages as deleted for this user (soft delete)
            conversation.messages.all().update(is_deleted=True)
            return JsonResponse({'success': True, 'message': 'Chat history cleared'})
        
        else:
            return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def get_new_messages_ajax(request, conversation_id):
    """
    AJAX endpoint to poll for new messages
    """
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        if not conversation.is_participant(request.user):
            return JsonResponse({'success': False, 'message': 'Permission denied'})
        
        # Get timestamp from request
        since_timestamp = request.GET.get('since')
        if since_timestamp:
            since_datetime = datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
        else:
            since_datetime = timezone.now() - timedelta(minutes=1)
        
        # Get new messages
        new_messages = Message.objects.filter(
            conversation=conversation,
            is_deleted=False,
            sent_at__gt=since_datetime
        ).exclude(sender=request.user).select_related('sender').order_by('sent_at')
        
        # Mark new messages as read
        new_messages.update(is_read=True)
        
        # Format messages for response
        messages_data = []
        for message in new_messages:
            messages_data.append({
                'id': str(message.id),
                'content': message.content,
                'sender_name': message.sender.get_display_name(),
                'sender_avatar': message.sender.avatar.url if message.sender.avatar else None,
                'sent_at': message.sent_at.strftime('%H:%M'),
                'message_type': message.message_type,
                'image_url': message.get_image_url(),
                'is_own_message': False
            })
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'has_new_messages': len(messages_data) > 0
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_POST
def delete_message_ajax(request, message_id):
    """
    AJAX endpoint to delete a message
    """
    try:
        message = get_object_or_404(Message, id=message_id)
        
        # Check if user can delete this message
        if not message.can_delete(request.user):
            return JsonResponse({'success': False, 'message': 'Cannot delete this message'})
        
        # Soft delete the message
        message.soft_delete()
        
        return JsonResponse({'success': True, 'message': 'Message deleted'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def typing_indicator_ajax(request, conversation_id):
    """
    AJAX endpoint for typing indicators
    """
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        if not conversation.is_participant(request.user):
            return JsonResponse({'success': False, 'message': 'Permission denied'})
        
        # This is a simple implementation - in production, you might want to use Redis
        # For now, we'll just return success
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def conversation_stats_view(request):
    """
    View for messaging statistics and analytics
    """
    # Get user's conversation statistics
    total_conversations = Conversation.objects.filter(
        Q(user1=request.user) | Q(user2=request.user),
        is_active=True
    ).count()
    
    total_messages_sent = Message.objects.filter(
        sender=request.user,
        is_deleted=False
    ).count()
    
    total_unread = 0
    conversations = Conversation.get_user_conversations(request.user)
    for conv in conversations:
        total_unread += conv.get_unread_count(request.user)
    
    # Recent activity (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_messages = Message.objects.filter(
        sender=request.user,
        sent_at__gte=week_ago,
        is_deleted=False
    ).count()
    
    context = {
        'total_conversations': total_conversations,
        'total_messages_sent': total_messages_sent,
        'total_unread': total_unread,
        'recent_messages': recent_messages,
        'title': 'Message Statistics'
    }
    
    return render(request, 'messaging/stats.html', context)


@login_required
def message_search_ajax(request):
    """
    AJAX endpoint for searching messages
    """
    try:
        query = request.GET.get('q', '').strip()
        conversation_id = request.GET.get('conversation_id')
        
        if not query:
            return JsonResponse({'success': False, 'message': 'Search query required'})
        
        # Base queryset
        messages_qs = Message.objects.filter(
            sender=request.user,
            is_deleted=False,
            content__icontains=query
        ).select_related('conversation', 'sender')
        
        # Filter by conversation if specified
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
                if conversation.is_participant(request.user):
                    messages_qs = messages_qs.filter(conversation=conversation)
                else:
                    return JsonResponse({'success': False, 'message': 'Permission denied'})
            except Conversation.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Conversation not found'})
        else:
            # Only search in conversations where user is participant
            user_conversations = Conversation.objects.filter(
                Q(user1=request.user) | Q(user2=request.user)
            )
            messages_qs = messages_qs.filter(conversation__in=user_conversations)
        
        # Limit results
        messages_qs = messages_qs.order_by('-sent_at')[:20]
        
        # Format results
        results = []
        for message in messages_qs:
            other_user = message.conversation.get_other_user(request.user)
            results.append({
                'id': str(message.id),
                'content': message.content[:100] + ('...' if len(message.content) > 100 else ''),
                'sent_at': message.sent_at.strftime('%Y-%m-%d %H:%M'),
                'conversation_id': str(message.conversation.id),
                'other_user_name': other_user.get_display_name() if other_user else 'Unknown',
                'other_user_avatar': other_user.avatar.url if other_user and other_user.avatar else None
            })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'total_found': len(results)
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_POST
def conversation_settings_ajax(request, conversation_id):
    """
    AJAX endpoint for updating conversation settings
    """
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        if not conversation.is_participant(request.user):
            return JsonResponse({'success': False, 'message': 'Permission denied'})
        
        data = json.loads(request.body)
        setting = data.get('setting')
        value = data.get('value')
        
        # Handle different settings
        if setting == 'muted':
            # Store muted status in cache (in production, use database)
            cache_key = f'conversation_muted_{conversation.id}_{request.user.id}'
            cache.set(cache_key, bool(value), timeout=86400 * 30)  # 30 days
            
            return JsonResponse({
                'success': True, 
                'message': 'Notifications ' + ('muted' if value else 'unmuted')
            })
        
        elif setting == 'archived':
            # Store archived status in cache
            cache_key = f'conversation_archived_{conversation.id}_{request.user.id}'
            cache.set(cache_key, bool(value), timeout=86400 * 365)  # 1 year
            
            return JsonResponse({
                'success': True, 
                'message': 'Conversation ' + ('archived' if value else 'unarchived')
            })
        
        else:
            return JsonResponse({'success': False, 'message': 'Invalid setting'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@csrf_exempt
def typing_status_ajax(request, conversation_id):
    """
    AJAX endpoint for typing status updates
    """
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        if not conversation.is_participant(request.user):
            return JsonResponse({'success': False, 'message': 'Permission denied'})
        
        if request.method == 'POST':
            # User is typing
            cache_key = f'typing_{conversation.id}_{request.user.id}'
            cache.set(cache_key, True, timeout=10)  # 10 seconds
            
            return JsonResponse({'success': True, 'status': 'typing'})
        
        elif request.method == 'GET':
            # Check if other user is typing
            other_user = conversation.get_other_user(request.user)
            if other_user:
                cache_key = f'typing_{conversation.id}_{other_user.id}'
                is_typing = cache.get(cache_key, False)
                
                return JsonResponse({
                    'success': True,
                    'is_typing': bool(is_typing),
                    'typing_user': other_user.get_display_name() if is_typing else None
                })
        
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
