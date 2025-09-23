"""
Comprehensive Admin Panel Views

This module contains all views for the admin panel with enhanced functionality,
security, and user management features.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, Http404, HttpResponseForbidden, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch, F, Sum, Avg, Max
from django.db import models, transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
import json
import re
import datetime
from collections import Counter
from datetime import timedelta

from .models import (
    AdminUser, UserWarning, AdminAction, BannedUser, 
    AdminSession, ModeratedContent, PlatformAnnouncement
)
from .auth import AdminAuthenticationBackend, AdminSessionManager
from .decorators import (
    admin_required, admin_permission_required, admin_role_required,
    log_admin_action, ajax_required, post_required, rate_limit
)
from .forms import (
    AdminLoginForm, UserSearchForm, UserBanForm, UserWarningForm,
    PostModerationForm, BulkActionForm, PlatformAnnouncementForm,
    AdminUserForm
)
from accounts.models import GupShupUser
from posts.models import Post
from social.models import Follow, Like, Comment

User = get_user_model()


# ================================
# Authentication Views
# ================================

def admin_login_view(request):
    """
    Enhanced admin login with security features
    """
    session_manager = AdminSessionManager()
    
    # Redirect if already logged in
    if session_manager.is_admin_authenticated(request):
        return redirect('admin_panel:dashboard')
    
    # Check if CAPTCHA is required (after multiple failed attempts)
    ip_address = session_manager._get_client_ip(request)
    failed_attempts = cache.get(f'admin_failed_attempts_{ip_address}', 0)
    require_captcha = failed_attempts >= 3
    
    if request.method == 'POST':
        form = AdminLoginForm(
            request.POST, 
            request=request,
            require_captcha=require_captcha
        )
        
        if form.is_valid():
            admin_user = form.get_admin_user()
            if admin_user:
                # Clear failed attempts on successful login
                cache.delete(f'admin_failed_attempts_{ip_address}')
                
                session_manager.login(request, admin_user)
                
                # Set extended session if "remember me" is checked
                if form.cleaned_data.get('remember_me'):
                    request.session.set_expiry(30 * 24 * 60 * 60)  # 30 days
                
                messages.success(
                    request, 
                    f'Welcome back, {admin_user.get_full_name()}! 🎉'
                )
                
                # Redirect to intended page or dashboard
                next_url = request.GET.get('next', 'admin_panel:dashboard')
                return redirect(next_url)
        else:
            # Increment failed attempts
            cache.set(f'admin_failed_attempts_{ip_address}', failed_attempts + 1, 3600)
            messages.error(request, 'Invalid credentials. Please try again.')
    else:
        form = AdminLoginForm(require_captcha=require_captcha)
    
    context = {
        'form': form,
        'require_captcha': require_captcha,
        'title': 'Admin Login',
        'failed_attempts': failed_attempts
    }
    
    return render(request, 'admin_panel/auth/login.html', context)


@admin_required
def admin_logout_view(request):
    """
    Secure admin logout with session cleanup
    """
    session_manager = AdminSessionManager()
    admin_user = session_manager.get_admin_from_session(request)
    
    session_manager.logout(request, admin_user)
    messages.success(request, 'You have been logged out successfully. Stay safe! 👋')
    return redirect('admin_panel:login')


@admin_required
def admin_password_change_view(request):
    """
    Admin password change view
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.admin_user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
        elif len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        else:
            request.admin_user.set_password(new_password)
            request.admin_user.save()
            
            # Log the password change
            AdminAction.objects.create(
                admin=request.admin_user,
                action_type='password_changed',
                severity='info',
                title='Password Changed',
                description='Admin changed their password',
                ip_address=AdminSessionManager()._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, 'Password changed successfully! Please login again.')
            return redirect('admin_panel:logout')
    
    context = {
        'title': 'Change Password'
    }
    
    return render(request, 'admin_panel/auth/change_password.html', context)


# ================================
# Dashboard Views
# ================================

def admin_dashboard_view(request):
    """
    GupShup Admin Dashboard - Fixed version
    """
    # Check if user is authenticated and is superuser
    if not request.user.is_authenticated or not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'You need admin privileges to access this page.')
        return redirect('/admin/login/?next=' + request.path)
    
    # Simple stats calculation with consistent queries
    total_users = GupShupUser.objects.count()
    active_users = GupShupUser.objects.filter(is_active=True).count()
    total_posts = Post.objects.count()
    
    # Get recent users and posts safely
    recent_users = GupShupUser.objects.select_related().order_by('-date_joined')[:5]
    recent_posts = Post.objects.select_related('author').order_by('-created_at')[:5]
    
    context = {
        'stats': {
            'users': {'total': total_users, 'active': active_users},
            'posts': {'total': total_posts}
        },
        'recent_users': recent_users,
        'recent_posts': recent_posts,
        'title': 'GupShup Admin Panel'
    }
    
    return render(request, 'admin_panel/simple_dashboard.html', context)


def admin_analytics_view(request):
    """
    Analytics & Reports Dashboard - Fixed version
    """
    # Check if user is authenticated and is superuser
    if not request.user.is_authenticated or not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'You need admin privileges to access this page.')
        return redirect('/admin/login/?next=' + request.path)
    
    # Imports local to function to avoid top-of-file changes
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    from collections import Counter
    from datetime import timedelta

    # Basic totals
    total_users = GupShupUser.objects.count()
    active_users = GupShupUser.objects.filter(is_active=True).count()
    total_posts = Post.objects.count()
    total_likes = Like.objects.count()
    total_comments = Comment.objects.count()

    # Time window for analytics
    days = 30
    start_date = timezone.now() - timedelta(days=days - 1)

    # User growth by day (last N days)
    user_growth_qs = (
        GupShupUser.objects
        .filter(date_joined__date__gte=start_date.date())
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    user_growth = list(user_growth_qs)

    # Trending hashtags from posts
    hashtag_counter = Counter()
    for tags in Post.objects.values_list('hashtags', flat=True):
        if tags:
            for tag in [t.strip() for t in tags.split(',') if t.strip()]:
                hashtag_counter[tag] += 1
    top_hashtags = hashtag_counter.most_common(10)

    # Engagement metrics
    engagement_stats = {
        'avg_posts_per_user': round((total_posts / total_users), 2) if total_users else 0.0,
        'avg_likes_per_post': round((total_likes / total_posts), 2) if total_posts else 0.0,
        'avg_comments_per_post': round((total_comments / total_posts), 2) if total_posts else 0.0,
    }

    # Today stats
    today = timezone.now().date()
    users_today = GupShupUser.objects.filter(date_joined__date=today).count()
    posts_today = Post.objects.filter(created_at__date=today).count()

    context = {
        'stats': {
            'total_users': total_users,
            'active_users': active_users,
            'total_posts': total_posts,
            'total_likes': total_likes,
            'total_comments': total_comments,
            'users_today': users_today,
            'posts_today': posts_today,
        },
        'user_growth': user_growth,
        'top_hashtags': top_hashtags,
        'engagement_stats': engagement_stats,
        'range_filter': days,
        'title': 'Analytics Dashboard',
    }

    return render(request, 'admin_panel/simple_analytics.html', context)


# ================================
# User Management Views
# ================================

def admin_users_view(request):
    """
    User Management Dashboard - Fixed version
    """
    # Check if user is authenticated and is superuser
    if not request.user.is_authenticated or not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'You need admin privileges to access this page.')
        return redirect('/admin/login/?next=' + request.path)
    
    # Get all users (model already has count fields)
    users = GupShupUser.objects.order_by('-date_joined')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Calculate stats
    total_count = users.count()
    active_count = users.filter(is_active=True).count()
    verified_count = users.filter(is_verified=True).count()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(users, 12)  # Show 12 users per page for better layout
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_count': total_count,
        'active_count': active_count,
        'verified_count': verified_count,
        'banned_count': 0,  # Simplified for now
        'search_query': search_query,
        'title': 'User Management'
    }
    
    return render(request, 'admin_panel/users/list.html', context)


def admin_user_detail_view(request, user_id):
    """
    Simple user detail view - redirects to Django admin for now
    """
    # Check if user is authenticated and is superuser
    if not request.user.is_authenticated or not request.user.is_superuser:
        from django.contrib import messages
        messages.error(request, 'You need admin privileges to access this page.')
        return redirect('/admin/login/?next=' + request.path)
    
    # For now, redirect to Django admin user edit page
    return redirect(f'/admin/accounts/gupshupuser/{user_id}/change/')


@admin_required
@admin_permission_required('ban_users')
@post_required
@log_admin_action('user_banned', severity='warning')
def admin_ban_user_view(request):
    """
    Ban a user with comprehensive options
    """
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(GupShupUser, id=user_id)
        
        form = UserBanForm(request.POST, user=user)
        
        if form.is_valid():
            # Check if user is already banned
            if hasattr(user, 'ban_record') and user.ban_record.is_active:
                return JsonResponse({
                    'success': False,
                    'error': 'User is already banned'
                })
            
            with transaction.atomic():
                # Create ban record
                ban_record = BannedUser.objects.create(
                    user=user,
                    admin=request.admin_user,
                    ban_type=form.cleaned_data['ban_type'],
                    reason=form.cleaned_data['reason'],
                    public_reason=form.cleaned_data['public_reason'],
                    expires_at=form.get_ban_expires_at(),
                    related_post_id=form.cleaned_data.get('related_post_id'),
                    ip_address=AdminSessionManager()._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    user_notified=form.cleaned_data['notify_user']
                )
                
                # Deactivate user account
                user.is_active = False
                user.save()
                
                # Log the action
                AdminAction.objects.create(
                    admin=request.admin_user,
                    action_type='user_banned',
                    severity='warning',
                    title=f'User Banned: {user.username}',
                    description=f'User {user.username} banned for: {form.cleaned_data["reason"]}',
                    target_user=user,
                    ip_address=AdminSessionManager()._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    metadata={
                        'ban_type': form.cleaned_data['ban_type'],
                        'duration': form.cleaned_data['duration'],
                        'public_reason': form.cleaned_data['public_reason']
                    }
                )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'User {user.username} has been banned successfully'
                })
            else:
                messages.success(request, f'User {user.username} has been banned successfully')
                return redirect('admin_panel:user_detail', user_id=user.id)
        
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@admin_required
@admin_permission_required('send_warnings')
@post_required
@log_admin_action('warning_issued', severity='info')
def admin_warn_user_view(request):
    """
    Issue a warning to a user
    """
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(GupShupUser, id=user_id)
        
        form = UserWarningForm(request.POST, user=user)
        
        if form.is_valid():
            with transaction.atomic():
                # Create warning
                warning = UserWarning.objects.create(
                    user=user,
                    admin=request.admin_user,
                    warning_type=form.cleaned_data['warning_type'],
                    severity=form.cleaned_data['severity'],
                    title=form.cleaned_data['title'],
                    message=form.cleaned_data['message'],
                    expires_at=form.cleaned_data['expires_at'],
                    auto_action=form.cleaned_data['auto_action'],
                    related_post=form.cleaned_data.get('related_post'),
                    email_sent=form.cleaned_data['send_email']
                )
                
                # Log the action
                AdminAction.objects.create(
                    admin=request.admin_user,
                    action_type='warning_issued',
                    severity='info',
                    title=f'Warning Issued: {user.username}',
                    description=f'Warning issued to {user.username}: {form.cleaned_data["title"]}',
                    target_user=user,
                    ip_address=AdminSessionManager()._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    metadata={
                        'warning_type': form.cleaned_data['warning_type'],
                        'severity': form.cleaned_data['severity'],
                        'warning_id': str(warning.id)
                    }
                )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Warning issued to {user.username} successfully'
                })
            else:
                messages.success(request, f'Warning issued to {user.username} successfully')
                return redirect('admin_panel:user_detail', user_id=user.id)
        
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# ================================
# Post Management Views
# ================================

@admin_required
@admin_permission_required('manage_posts')
def admin_posts_view(request):
    """
    Enhanced post management with filtering
    """
    search = request.GET.get('search', '')
    content_type = request.GET.get('type', '')
    privacy = request.GET.get('privacy', '')
    sort_by = request.GET.get('sort', '-created_at')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Build queryset
    posts = Post.objects.select_related('author').prefetch_related('media_files')
    
    # Apply filters
    if search:
        posts = posts.filter(
            Q(content__icontains=search) |
            Q(author__username__icontains=search) |
            Q(hashtags__icontains=search) |
            Q(location__icontains=search)
        )
    
    if content_type:
        if content_type == 'text':
            posts = posts.filter(media_files__isnull=True)
        elif content_type == 'image':
            posts = posts.filter(media_files__media_type='image')
        elif content_type == 'video':
            posts = posts.filter(media_files__media_type='video')
    
    if privacy:
        posts = posts.filter(privacy=privacy)
    
    if date_from:
        try:
            from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            posts = posts.filter(created_at__date__gte=from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            posts = posts.filter(created_at__date__lte=to_date)
        except ValueError:
            pass
    
    # Apply sorting
    posts = posts.order_by(sort_by)
    
    # Get flagged posts count for badge
    flagged_posts_count = ModeratedContent.objects.filter(
        content_type='post',
        status='pending'
    ).count()
    
    # Pagination
    paginator = Paginator(posts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'content_type': content_type,
        'privacy': privacy,
        'sort_by': sort_by,
        'date_from': date_from,
        'date_to': date_to,
        'flagged_posts_count': flagged_posts_count,
        'total_count': paginator.count,
        'title': 'Post Management'
    }
    
    return render(request, 'admin_panel/posts/list.html', context)


@admin_required
@admin_permission_required('delete_posts')
@ajax_required
@post_required
@log_admin_action('post_deleted', severity='warning')
def admin_delete_post_ajax(request):
    """
    Delete a post via AJAX with logging
    """
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        reason = data.get('reason', 'Inappropriate content')
        
        post = get_object_or_404(Post, id=post_id)
        post_author = post.author
        post_content = post.content[:100]  # Keep snippet for logs
        
        with transaction.atomic():
            # Log action before deletion
            AdminAction.objects.create(
                admin=request.admin_user,
                action_type='post_deleted',
                severity='warning',
                title=f'Post Deleted: {post_author.username}',
                description=f'Deleted post by {post_author.username}: {reason}',
                target_user=post_author,
                ip_address=AdminSessionManager()._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'post_content_preview': post_content,
                    'deletion_reason': reason,
                    'post_privacy': post.privacy
                }
            )
            
            # Delete the post
            post.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Post deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })



# ================================
# Content Moderation Views
# ================================

@admin_required
@admin_permission_required('moderate_content')
def admin_moderation_queue_view(request):
    """
    Content moderation queue with priority sorting
    """
    # Get filter parameters
    status_filter = request.GET.get('status', 'pending')
    content_type_filter = request.GET.get('content_type', 'all')
    severity_filter = request.GET.get('severity', 'all')
    sort_by = request.GET.get('sort', '-flagged_at')
    
    # Build queryset
    moderated_content = ModeratedContent.objects.all()
    
    # Apply filters
    if status_filter != 'all':
        moderated_content = moderated_content.filter(status=status_filter)
    
    if content_type_filter != 'all':
        moderated_content = moderated_content.filter(content_type=content_type_filter)
    
    if severity_filter != 'all':
        moderated_content = moderated_content.filter(severity=severity_filter)
    
    # Apply sorting with priority
    if sort_by == 'priority':
        # Custom priority: critical -> high -> medium -> low, then by date
        moderated_content = moderated_content.extra(
            select={
                'priority_order': "CASE "
                                 "WHEN severity='critical' THEN 1 "
                                 "WHEN severity='high' THEN 2 "
                                 "WHEN severity='medium' THEN 3 "
                                 "WHEN severity='low' THEN 4 "
                                 "ELSE 5 END"
            }
        ).order_by('priority_order', '-flagged_at')
    else:
        moderated_content = moderated_content.order_by(sort_by)
    
    # Add related content information
    moderated_items = []
    for item in moderated_content[:200]:  # Limit for performance
        content_obj = None
        content_preview = ""
        author = None
        
        try:
            if item.content_type == 'post':
                content_obj = Post.objects.select_related('author').get(id=item.object_id)
                content_preview = content_obj.content[:200]
                author = content_obj.author
            elif item.content_type == 'comment':
                content_obj = Comment.objects.select_related('user', 'post').get(id=item.object_id)
                content_preview = content_obj.text[:200]
                author = content_obj.user
            
            moderated_items.append({
                'moderation': item,
                'content': content_obj,
                'preview': content_preview,
                'author': author
            })
        except (Post.DoesNotExist, Comment.DoesNotExist):
            # Content was deleted, mark as resolved
            item.status = 'resolved'
            item.review_notes = 'Content no longer exists'
            item.save()
    
    # Pagination
    paginator = Paginator(moderated_items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get summary statistics
    queue_stats = {
        'total_pending': ModeratedContent.objects.filter(status='pending').count(),
        'total_flagged': ModeratedContent.objects.filter(status='flagged').count(),
        'critical_count': ModeratedContent.objects.filter(
            status='pending', severity='critical'
        ).count(),
        'high_count': ModeratedContent.objects.filter(
            status='pending', severity='high'
        ).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'queue_stats': queue_stats,
        'status_filter': status_filter,
        'content_type_filter': content_type_filter,
        'severity_filter': severity_filter,
        'sort_by': sort_by,
        'title': 'Content Moderation Queue'
    }
    
    return render(request, 'admin_panel/moderation/queue.html', context)


@admin_required
@admin_permission_required('moderate_content')
@ajax_required
@post_required
def admin_moderate_content_ajax(request):
    """
    Take moderation action on content via AJAX
    """
    try:
        data = json.loads(request.body)
        moderation_id = data.get('moderation_id')
        action = data.get('action')  # approve, delete, flag, ignore
        reason = data.get('reason', '')
        severity = data.get('severity', 'medium')
        
        moderation = get_object_or_404(ModeratedContent, id=moderation_id)
        
        # Get the actual content object
        content_obj = None
        if moderation.content_type == 'post':
            content_obj = Post.objects.get(id=moderation.object_id)
        elif moderation.content_type == 'comment':
            content_obj = Comment.objects.get(id=moderation.object_id)
        
        if not content_obj:
            return JsonResponse({
                'success': False,
                'error': 'Content no longer exists'
            })
        
        with transaction.atomic():
            # Perform action
            if action == 'approve':
                moderation.status = 'approved'
                moderation.reviewed_by = request.admin_user
                moderation.reviewed_at = timezone.now()
                moderation.review_notes = reason or 'Content approved'
                action_type = 'content_approved'
                
            elif action == 'delete':
                moderation.status = 'deleted'
                moderation.reviewed_by = request.admin_user
                moderation.reviewed_at = timezone.now()
                moderation.review_notes = reason or 'Content deleted for policy violation'
                
                # Delete the actual content
                content_obj.delete()
                action_type = 'content_deleted'
                
            elif action == 'flag':
                moderation.status = 'flagged'
                moderation.severity = severity
                moderation.flag_reason = reason or 'Content flagged for review'
                moderation.flagged_by = request.admin_user
                moderation.flagged_at = timezone.now()
                action_type = 'content_flagged'
                
            elif action == 'ignore':
                moderation.status = 'ignored'
                moderation.reviewed_by = request.admin_user
                moderation.reviewed_at = timezone.now()
                moderation.review_notes = reason or 'Content ignored'
                action_type = 'content_ignored'
                
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action'
                })
            
            moderation.save()
            
            # Log the action
            AdminAction.objects.create(
                admin=request.admin_user,
                action_type=action_type,
                severity='info' if action == 'approve' else 'warning',
                title=f'Content {action.title()}: {moderation.content_type}',
                description=f'{action.title()} {moderation.content_type} by {content_obj.author.username if hasattr(content_obj, "author") else "user"}: {reason}',
                target_user=content_obj.author if hasattr(content_obj, 'author') else content_obj.user,
                ip_address=AdminSessionManager()._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'moderation_id': str(moderation.id),
                    'content_type': moderation.content_type,
                    'content_id': moderation.object_id,
                    'action': action,
                    'severity': severity
                }
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Content {action}ed successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@admin_required
@admin_permission_required('moderate_content')
def admin_bulk_moderation_view(request):
    """
    Bulk content moderation actions
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        content_ids = request.POST.getlist('content_ids')
        reason = request.POST.get('reason', '')
        
        if not content_ids:
            messages.error(request, 'No content selected')
            return redirect('admin_panel:moderation_queue')
        
        success_count = 0
        error_count = 0
        
        with transaction.atomic():
            for content_id in content_ids:
                try:
                    moderation = ModeratedContent.objects.get(id=content_id)
                    
                    if action == 'bulk_approve':
                        moderation.status = 'approved'
                        moderation.reviewed_by = request.admin_user
                        moderation.reviewed_at = timezone.now()
                        moderation.review_notes = reason or 'Bulk approved'
                        
                    elif action == 'bulk_delete':
                        moderation.status = 'deleted'
                        moderation.reviewed_by = request.admin_user
                        moderation.reviewed_at = timezone.now()
                        moderation.review_notes = reason or 'Bulk deleted'
                        
                        # Delete actual content
                        try:
                            if moderation.content_type == 'post':
                                Post.objects.get(id=moderation.object_id).delete()
                            elif moderation.content_type == 'comment':
                                Comment.objects.get(id=moderation.object_id).delete()
                        except (Post.DoesNotExist, Comment.DoesNotExist):
                            pass  # Content already deleted
                    
                    elif action == 'bulk_flag':
                        moderation.status = 'flagged'
                        moderation.flagged_by = request.admin_user
                        moderation.flagged_at = timezone.now()
                        moderation.flag_reason = reason or 'Bulk flagged'
                    
                    moderation.save()
                    success_count += 1
                    
                except ModeratedContent.DoesNotExist:
                    error_count += 1
                    continue
            
            # Log bulk action
            AdminAction.objects.create(
                admin=request.admin_user,
                action_type='bulk_moderation',
                severity='info',
                title=f'Bulk {action.replace("bulk_", "").title()}',
                description=f'Bulk {action.replace("bulk_", "")} performed on {success_count} items',
                ip_address=AdminSessionManager()._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'action': action,
                    'items_processed': success_count,
                    'errors': error_count,
                    'reason': reason
                }
            )
        
        messages.success(
            request,
            f'Bulk action completed: {success_count} items processed'
            + (f', {error_count} errors' if error_count > 0 else '')
        )
    
    return redirect('admin_panel:moderation_queue')


@admin_required
@admin_permission_required('moderate_content')
def admin_automated_flagging_view(request):
    """
    Configure automated content flagging rules
    """
    # Predefined flagging rules
    flagging_rules = {
        'inappropriate_keywords': {
            'name': 'Inappropriate Keywords',
            'description': 'Flag content containing inappropriate language',
            'keywords': [
                'spam', 'fake', 'scam', 'fraud', 'hate', 'abuse',
                'violence', 'harassment', 'threat', 'illegal'
            ],
            'indian_terms': [
                'bhakchod', 'gandu', 'chutiya', 'madarchod', 'bhenchod',
                'randi', 'saala', 'kamina', 'harami'
            ],
            'enabled': True,
            'severity': 'medium'
        },
        'excessive_caps': {
            'name': 'Excessive Capitalization',
            'description': 'Flag content with too many capital letters',
            'threshold': 50,  # percentage
            'enabled': True,
            'severity': 'low'
        },
        'spam_patterns': {
            'name': 'Spam Patterns',
            'description': 'Flag content with spam-like patterns',
            'patterns': [
                r'(.)\1{5,}',  # Repeated characters
                r'[!@#$%^&*]{5,}',  # Excessive special chars
                r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'  # URLs
            ],
            'enabled': True,
            'severity': 'medium'
        },
        'new_user_content': {
            'name': 'New User Content Review',
            'description': 'Flag content from users registered less than 7 days ago',
            'days_threshold': 7,
            'enabled': False,
            'severity': 'low'
        }
    }
    
    if request.method == 'POST':
        # Process rule updates
        for rule_key, rule_data in flagging_rules.items():
            enabled = request.POST.get(f'{rule_key}_enabled') == 'on'
            severity = request.POST.get(f'{rule_key}_severity', rule_data['severity'])
            
            # Store updated settings (in a real app, this would be in database/cache)
            cache.set(f'flagging_rule_{rule_key}_enabled', enabled, 86400)
            cache.set(f'flagging_rule_{rule_key}_severity', severity, 86400)
        
        messages.success(request, 'Automated flagging rules updated successfully')
        return redirect('admin_panel:automated_flagging')
    
    # Load current settings from cache
    for rule_key, rule_data in flagging_rules.items():
        rule_data['enabled'] = cache.get(f'flagging_rule_{rule_key}_enabled', rule_data['enabled'])
        rule_data['severity'] = cache.get(f'flagging_rule_{rule_key}_severity', rule_data['severity'])
    
    context = {
        'flagging_rules': flagging_rules,
        'title': 'Automated Content Flagging'
    }
    
    return render(request, 'admin_panel/moderation/automated_flagging.html', context)


@admin_required
@admin_permission_required('moderate_content')
def run_content_scan(request):
    """
    Run automated content scanning for flagging
    """
    if request.method == 'POST':
        # Get scan parameters
        days_back = int(request.POST.get('days_back', 7))
        content_type = request.POST.get('content_type', 'both')
        
        flagged_count = 0
        scanned_count = 0
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Inappropriate keywords from rules
        inappropriate_keywords = [
            'spam', 'fake', 'scam', 'fraud', 'hate', 'abuse',
            'violence', 'harassment', 'threat', 'illegal',
            'bhakchod', 'gandu', 'chutiya', 'madarchod', 'bhenchod',
            'randi', 'saala', 'kamina', 'harami'
        ]
        
        # Scan posts
        if content_type in ['posts', 'both']:
            posts_to_scan = Post.objects.filter(
                created_at__gte=cutoff_date
            ).exclude(
                moderated_content__status__in=['approved', 'deleted']
            )
            
            for post in posts_to_scan:
                scanned_count += 1
                should_flag = False
                flag_reasons = []
                severity = 'low'
                
                content_lower = post.content.lower()
                
                # Check inappropriate keywords
                for keyword in inappropriate_keywords:
                    if keyword in content_lower:
                        should_flag = True
                        flag_reasons.append(f'Contains inappropriate keyword: {keyword}')
                        severity = 'medium'
                        break
                
                # Check excessive capitalization
                if post.content:
                    caps_ratio = sum(1 for c in post.content if c.isupper()) / len(post.content)
                    if caps_ratio > 0.5:
                        should_flag = True
                        flag_reasons.append('Excessive capitalization')
                        severity = max(severity, 'low', key=['low', 'medium', 'high'].index)
                
                # Check spam patterns
                spam_patterns = [
                    r'(.)\1{5,}',  # Repeated characters
                    r'[!@#$%^&*]{5,}',  # Excessive special chars
                ]
                
                for pattern in spam_patterns:
                    if re.search(pattern, post.content):
                        should_flag = True
                        flag_reasons.append('Spam pattern detected')
                        severity = 'medium'
                        break
                
                # Flag if needed
                if should_flag:
                    ModeratedContent.objects.update_or_create(
                        content_type='post',
                        object_id=post.id,
                        defaults={
                            'status': 'flagged',
                            'severity': severity,
                            'flag_reason': '; '.join(flag_reasons),
                            'auto_flagged': True,
                            'flagged_at': timezone.now(),
                            'notes': f'Auto-flagged by content scan'
                        }
                    )
                    flagged_count += 1
        
        # Scan comments (similar logic)
        if content_type in ['comments', 'both']:
            comments_to_scan = Comment.objects.filter(
                created_at__gte=cutoff_date
            ).exclude(
                moderated_content__status__in=['approved', 'deleted']
            )
            
            for comment in comments_to_scan:
                scanned_count += 1
                should_flag = False
                flag_reasons = []
                severity = 'low'
                
                content_lower = comment.text.lower()
                
                # Apply similar checks as posts
                for keyword in inappropriate_keywords:
                    if keyword in content_lower:
                        should_flag = True
                        flag_reasons.append(f'Contains inappropriate keyword: {keyword}')
                        severity = 'medium'
                        break
                
                if should_flag:
                    ModeratedContent.objects.update_or_create(
                        content_type='comment',
                        object_id=comment.id,
                        defaults={
                            'status': 'flagged',
                            'severity': severity,
                            'flag_reason': '; '.join(flag_reasons),
                            'auto_flagged': True,
                            'flagged_at': timezone.now(),
                            'notes': f'Auto-flagged by content scan'
                        }
                    )
                    flagged_count += 1
        
        # Log the scan
        AdminAction.objects.create(
            admin=request.admin_user,
            action_type='content_scan',
            severity='info',
            title='Automated Content Scan',
            description=f'Scanned {scanned_count} items, flagged {flagged_count} for review',
            ip_address=AdminSessionManager()._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata={
                'scanned_count': scanned_count,
                'flagged_count': flagged_count,
                'days_back': days_back,
                'content_type': content_type
            }
        )
        
        messages.success(
            request,
            f'Content scan completed: {scanned_count} items scanned, {flagged_count} flagged for review'
        )
        
        return redirect('admin_panel:moderation_queue')
    
    context = {
        'title': 'Run Content Scan'
    }
    
    return render(request, 'admin_panel/moderation/run_scan.html', context)


@admin_required
@admin_permission_required('moderate_content')
def admin_moderation_export_view(request):
    """
    Export moderation data for compliance reporting
    """
    if request.method == 'POST':
        export_format = request.POST.get('format', 'csv')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        status_filter = request.POST.get('status', 'all')
        
        # Build queryset
        moderation_data = ModeratedContent.objects.all()
        
        if date_from:
            try:
                from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
                moderation_data = moderation_data.filter(flagged_at__date__gte=from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                moderation_data = moderation_data.filter(flagged_at__date__lte=to_date)
            except ValueError:
                pass
        
        if status_filter != 'all':
            moderation_data = moderation_data.filter(status=status_filter)
        
        moderation_data = moderation_data.select_related('flagged_by', 'reviewed_by').order_by('-flagged_at')
        
        # Generate export
        if export_format == 'csv':
            import csv
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="moderation_export_{timezone.now().strftime("%Y%m%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'ID', 'Content Type', 'Object ID', 'Status', 'Severity',
                'Flag Reason', 'Flagged By', 'Flagged At', 'Reviewed By',
                'Reviewed At', 'Review Notes', 'Auto Flagged'
            ])
            
            for item in moderation_data:
                writer.writerow([
                    item.id,
                    item.content_type,
                    item.object_id,
                    item.status,
                    item.severity,
                    item.flag_reason or '',
                    item.flagged_by.username if item.flagged_by else '',
                    item.flagged_at.strftime('%Y-%m-%d %H:%M:%S') if item.flagged_at else '',
                    item.reviewed_by.username if item.reviewed_by else '',
                    item.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if item.reviewed_at else '',
                    item.review_notes or '',
                    'Yes' if item.auto_flagged else 'No'
                ])
            
            # Log export
            AdminAction.objects.create(
                admin=request.admin_user,
                action_type='moderation_export',
                severity='info',
                title='Moderation Data Export',
                description=f'Exported {moderation_data.count()} moderation records',
                ip_address=AdminSessionManager()._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'export_format': export_format,
                    'record_count': moderation_data.count(),
                    'date_from': date_from or '',
                    'date_to': date_to or '',
                    'status_filter': status_filter
                }
            )
            
            return response
        
        elif export_format == 'json':
            import json
            response = HttpResponse(content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="moderation_export_{timezone.now().strftime("%Y%m%d")}.json"'
            
            data = []
            for item in moderation_data:
                data.append({
                    'id': item.id,
                    'content_type': item.content_type,
                    'object_id': item.object_id,
                    'status': item.status,
                    'severity': item.severity,
                    'flag_reason': item.flag_reason or '',
                    'flagged_by': item.flagged_by.username if item.flagged_by else '',
                    'flagged_at': item.flagged_at.isoformat() if item.flagged_at else '',
                    'reviewed_by': item.reviewed_by.username if item.reviewed_by else '',
                    'reviewed_at': item.reviewed_at.isoformat() if item.reviewed_at else '',
                    'review_notes': item.review_notes or '',
                    'auto_flagged': item.auto_flagged
                })
            
            response.write(json.dumps(data, indent=2))
            return response
    
    context = {
        'title': 'Export Moderation Data'
    }
    
    return render(request, 'admin_panel/moderation/export.html', context)
