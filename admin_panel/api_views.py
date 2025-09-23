"""
GupShup Admin Panel API Views

This module provides AJAX endpoints and RESTful API views for the admin panel,
enabling real-time updates, bulk operations, and dynamic content management.
"""

import json
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any

from django.http import JsonResponse, HttpResponse, Http404, StreamingHttpResponse
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, F, Sum, Avg, Max, Min
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model

from accounts.models import GupShupUser
from posts.models import Post
from social.models import Follow, Comment, Like
from .models import AdminUser, AdminAction, UserWarning, BannedUser, ModeratedContent, AdminSession
from .decorators import admin_required, admin_permission_required, ajax_required, rate_limit
from .analytics import (
    UserAnalytics, PostAnalytics, GeographicAnalytics, 
    EngagementMetrics, ReportGenerator, get_dashboard_analytics
)
from .auth import AdminSessionManager


class AdminAPIView(View):
    """Base class for admin API views with common functionality"""
    
    @method_decorator(admin_required)
    @method_decorator(ajax_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def json_response(self, data: Any, status: int = 200) -> JsonResponse:
        """Return JSON response with proper formatting"""
        return JsonResponse({
            'success': status < 400,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }, status=status)
    
    def error_response(self, message: str, status: int = 400) -> JsonResponse:
        """Return error JSON response"""
        return JsonResponse({
            'success': False,
            'error': message,
            'timestamp': timezone.now().isoformat()
        }, status=status)
    
    def paginated_response(self, queryset, page: int, per_page: int = 20) -> Dict:
        """Return paginated data with metadata"""
        paginator = Paginator(queryset, per_page)
        
        try:
            page_obj = paginator.page(page)
        except (EmptyPage, PageNotAnInteger):
            page_obj = paginator.page(1)
        
        return {
            'items': list(page_obj.object_list.values()) if hasattr(page_obj.object_list, 'values') else list(page_obj.object_list),
            'pagination': {
                'page': page_obj.number,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        }


# ================================
# Dashboard and Statistics APIs
# ================================

class DashboardStatsAPI(AdminAPIView):
    """API endpoint for dashboard statistics"""
    
    def get(self, request):
        """Get real-time dashboard statistics"""
        try:
            days = int(request.GET.get('days', 7))
            force_refresh = request.GET.get('refresh') == 'true'
            
            cache_key = f'dashboard_stats_{days}'
            
            if not force_refresh:
                cached_data = cache.get(cache_key)
                if cached_data:
                    return self.json_response(cached_data)
            
            # Get comprehensive dashboard data
            analytics_data = get_dashboard_analytics(days)
            
            # Add real-time statistics
            now = timezone.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            real_time_stats = {
                'users_online_now': self._get_online_users_count(),
                'posts_today': Post.objects.filter(created_at__gte=today_start).count(),
                'comments_today': Comment.objects.filter(created_at__gte=today_start).count(),
                'likes_today': Like.objects.filter(created_at__gte=today_start).count(),
                'pending_moderation': ModeratedContent.objects.filter(status='pending').count(),
                'active_warnings': UserWarning.objects.filter(status='active').count(),
                'active_bans': BannedUser.objects.filter(is_active=True).count(),
                'admin_sessions': AdminSession.objects.filter(
                    is_active=True,
                    expires_at__gt=now
                ).count()
            }
            
            # Combine analytics with real-time stats
            dashboard_data = {
                **analytics_data,
                'real_time': real_time_stats,
                'last_updated': now.isoformat()
            }
            
            # Cache for 2 minutes
            cache.set(cache_key, dashboard_data, 120)
            
            return self.json_response(dashboard_data)
            
        except Exception as e:
            return self.error_response(f'Error fetching dashboard stats: {str(e)}', 500)
    
    def _get_online_users_count(self) -> int:
        """Get count of users online in the last 15 minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=15)
        return GupShupUser.objects.filter(
            last_login__gte=cutoff_time,
            is_active=True
        ).count()


class AnalyticsAPI(AdminAPIView):
    """API endpoint for detailed analytics"""
    
    @admin_permission_required('view_analytics')
    def get(self, request):
        """Get detailed analytics data"""
        try:
            analytics_type = request.GET.get('type', 'comprehensive')
            days = int(request.GET.get('days', 30))
            
            if analytics_type == 'user_growth':
                user_analytics = UserAnalytics()
                data = user_analytics.get_user_growth_data(days)
                
            elif analytics_type == 'content_metrics':
                post_analytics = PostAnalytics()
                data = post_analytics.get_content_metrics(days)
                
            elif analytics_type == 'geographic':
                geo_analytics = GeographicAnalytics()
                data = geo_analytics.get_geographic_distribution()
                
            elif analytics_type == 'engagement':
                engagement_metrics = EngagementMetrics()
                data = engagement_metrics.get_platform_engagement_summary(days)
                
            elif analytics_type == 'hashtags':
                post_analytics = PostAnalytics()
                data = post_analytics.get_hashtag_analytics(days)
                
            elif analytics_type == 'viral':
                post_analytics = PostAnalytics()
                data = post_analytics.get_viral_content_analysis(min(days, 7))
                
            else:  # comprehensive
                report_generator = ReportGenerator()
                data = report_generator.generate_comprehensive_report(days)
            
            return self.json_response(data)
            
        except Exception as e:
            return self.error_response(f'Error fetching analytics: {str(e)}', 500)


# ================================
# User Management APIs
# ================================

class UserSearchAPI(AdminAPIView):
    """API endpoint for user search with advanced filtering"""
    
    @admin_permission_required('manage_users')
    def get(self, request):
        """Search users with filters"""
        try:
            query = request.GET.get('q', '').strip()
            status = request.GET.get('status', 'all')
            state = request.GET.get('state', '')
            verified = request.GET.get('verified', '')
            page = int(request.GET.get('page', 1))
            per_page = min(int(request.GET.get('per_page', 20)), 100)
            
            # Build base queryset
            users = GupShupUser.objects.all()
            
            # Apply search query
            if query:
                users = users.filter(
                    Q(username__icontains=query) |
                    Q(email__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query) |
                    Q(phone_number__icontains=query)
                )
            
            # Apply status filter
            if status == 'active':
                users = users.filter(is_active=True)
            elif status == 'inactive':
                users = users.filter(is_active=False)
            elif status == 'banned':
                banned_ids = BannedUser.objects.filter(is_active=True).values_list('user_id', flat=True)
                users = users.filter(id__in=banned_ids)
            elif status == 'verified':
                users = users.filter(is_verified=True)
            
            # Apply state filter
            if state:
                users = users.filter(state__iexact=state)
            
            # Apply verification filter
            if verified == 'true':
                users = users.filter(is_verified=True)
            elif verified == 'false':
                users = users.filter(is_verified=False)
            
            # Annotate with additional data
            users = users.select_related().annotate(
                posts_count=Count('posts'),
                warnings_count=Count('warnings', filter=Q(warnings__status='active')),
                followers_count=Count('followers', filter=Q(followers__status='accepted'))
            ).order_by('-date_joined')
            
            # Get paginated results
            paginated_data = self.paginated_response(users, page, per_page)
            
            # Add ban status to each user
            banned_user_ids = set(
                BannedUser.objects.filter(is_active=True).values_list('user_id', flat=True)
            )
            
            for user in paginated_data['items']:
                user['is_banned'] = user['id'] in banned_user_ids
                user['avatar_url'] = f"/media/avatars/{user['id']}.jpg"  # Placeholder
                user['full_name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                user['location'] = f"{user.get('city', '')}, {user.get('state', '')}".strip(', ')
            
            return self.json_response(paginated_data)
            
        except Exception as e:
            return self.error_response(f'Error searching users: {str(e)}', 500)


class UserDetailAPI(AdminAPIView):
    """API endpoint for detailed user information"""
    
    @admin_permission_required('manage_users')
    def get(self, request, user_id):
        """Get detailed user information"""
        try:
            user = GupShupUser.objects.select_related().get(id=user_id)
            
            # Get user statistics
            user_stats = {
                'posts_count': user.posts.count(),
                'comments_count': user.comment_set.count(),
                'likes_given': Like.objects.filter(user=user).count(),
                'likes_received': Like.objects.filter(post__author=user).count(),
                'followers_count': user.followers.filter(status='accepted').count(),
                'following_count': user.following.filter(status='accepted').count(),
                'warnings_count': user.warnings.filter(status='active').count(),
                'total_warnings': user.warnings.count()
            }
            
            # Get recent activity
            recent_posts = list(
                user.posts.order_by('-created_at')[:10]
                .values('id', 'content', 'created_at', 'likes_count', 'comments_count')
            )
            
            recent_comments = list(
                user.comment_set.select_related('post')
                .order_by('-created_at')[:10]
                .values('id', 'text', 'created_at', 'post__id', 'post__content')
            )
            
            # Get warnings
            warnings = list(
                user.warnings.select_related('admin')
                .order_by('-created_at')[:5]
                .values('id', 'warning_type', 'severity', 'title', 'message', 'created_at', 'admin__username')
            )
            
            # Get ban information
            try:
                ban_record = user.ban_record
                ban_info = {
                    'is_banned': ban_record.is_active,
                    'ban_type': ban_record.ban_type,
                    'banned_at': ban_record.banned_at.isoformat(),
                    'expires_at': ban_record.expires_at.isoformat() if ban_record.expires_at else None,
                    'reason': ban_record.reason,
                    'admin': ban_record.admin.username if ban_record.admin else None
                }
            except BannedUser.DoesNotExist:
                ban_info = {'is_banned': False}
            
            # Prepare user data
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.get_full_name(),
                'phone_number': user.phone_number,
                'city': user.city,
                'state': user.state,
                'bio': user.bio,
                'is_active': user.is_active,
                'is_verified': user.is_verified,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'profile_picture': user.profile_picture.url if user.profile_picture else None,
                'stats': user_stats,
                'recent_posts': recent_posts,
                'recent_comments': recent_comments,
                'warnings': warnings,
                'ban_info': ban_info
            }
            
            return self.json_response(user_data)
            
        except GupShupUser.DoesNotExist:
            return self.error_response('User not found', 404)
        except Exception as e:
            return self.error_response(f'Error fetching user details: {str(e)}', 500)


class UserTimelineAPI(AdminAPIView):
    """API endpoint for user activity timeline"""
    
    @admin_permission_required('manage_users')
    def get(self, request, user_id):
        """Get user activity timeline"""
        try:
            user = GupShupUser.objects.get(id=user_id)
            days = int(request.GET.get('days', 30))
            page = int(request.GET.get('page', 1))
            
            start_date = timezone.now() - timedelta(days=days)
            
            # Get all activity types
            activities = []
            
            # Posts
            posts = user.posts.filter(created_at__gte=start_date).values(
                'id', 'content', 'created_at', 'likes_count', 'comments_count'
            )
            for post in posts:
                activities.append({
                    'type': 'post',
                    'id': post['id'],
                    'content': post['content'][:100] + '...' if len(post['content']) > 100 else post['content'],
                    'created_at': post['created_at'],
                    'metadata': {
                        'likes': post['likes_count'],
                        'comments': post['comments_count']
                    }
                })
            
            # Comments
            comments = user.comment_set.filter(created_at__gte=start_date).select_related('post').values(
                'id', 'text', 'created_at', 'post__id', 'post__content'
            )
            for comment in comments:
                activities.append({
                    'type': 'comment',
                    'id': comment['id'],
                    'content': comment['text'][:100] + '...' if len(comment['text']) > 100 else comment['text'],
                    'created_at': comment['created_at'],
                    'metadata': {
                        'post_id': comment['post__id'],
                        'post_preview': comment['post__content'][:50] + '...' if comment['post__content'] and len(comment['post__content']) > 50 else comment['post__content']
                    }
                })
            
            # Warnings received
            warnings = user.warnings.filter(created_at__gte=start_date).select_related('admin').values(
                'id', 'warning_type', 'title', 'created_at', 'admin__username'
            )
            for warning in warnings:
                activities.append({
                    'type': 'warning',
                    'id': warning['id'],
                    'content': f"Warning: {warning['title']}",
                    'created_at': warning['created_at'],
                    'metadata': {
                        'warning_type': warning['warning_type'],
                        'admin': warning['admin__username']
                    }
                })
            
            # Sort by date (most recent first)
            activities.sort(key=lambda x: x['created_at'], reverse=True)
            
            # Paginate results
            paginated_data = self.paginated_response(activities, page, 50)
            
            return self.json_response(paginated_data)
            
        except GupShupUser.DoesNotExist:
            return self.error_response('User not found', 404)
        except Exception as e:
            return self.error_response(f'Error fetching user timeline: {str(e)}', 500)


# ================================
# Content Moderation APIs
# ================================

class ModerationQueueAPI(AdminAPIView):
    """API endpoint for content moderation queue"""
    
    @admin_permission_required('moderate_content')
    def get(self, request):
        """Get moderation queue with filtering"""
        try:
            status = request.GET.get('status', 'pending')
            content_type = request.GET.get('content_type', 'all')
            severity = request.GET.get('severity', 'all')
            page = int(request.GET.get('page', 1))
            per_page = min(int(request.GET.get('per_page', 20)), 100)
            
            # Build queryset
            moderated_content = ModeratedContent.objects.select_related(
                'flagged_by', 'reviewed_by'
            )
            
            # Apply filters
            if status != 'all':
                moderated_content = moderated_content.filter(status=status)
            
            if content_type != 'all':
                moderated_content = moderated_content.filter(content_type=content_type)
            
            if severity != 'all':
                moderated_content = moderated_content.filter(severity=severity)
            
            # Order by priority and date
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
            
            # Get paginated results
            paginated_data = self.paginated_response(moderated_content, page, per_page)
            
            # Add content preview for each item
            for item in paginated_data['items']:
                try:
                    if item['content_type'] == 'post':
                        post = Post.objects.get(id=item['object_id'])
                        item['content_preview'] = post.content[:200] + '...' if len(post.content) > 200 else post.content
                        item['author'] = post.author.username
                        item['author_id'] = post.author.id
                    elif item['content_type'] == 'comment':
                        comment = Comment.objects.get(id=item['object_id'])
                        item['content_preview'] = comment.text[:200] + '...' if len(comment.text) > 200 else comment.text
                        item['author'] = comment.user.username
                        item['author_id'] = comment.user.id
                except (Post.DoesNotExist, Comment.DoesNotExist):
                    item['content_preview'] = '[Content no longer exists]'
                    item['author'] = 'Unknown'
                    item['author_id'] = None
                
                # Format dates
                if item['flagged_at']:
                    item['flagged_at'] = item['flagged_at'].isoformat() if hasattr(item['flagged_at'], 'isoformat') else item['flagged_at']
                if item['reviewed_at']:
                    item['reviewed_at'] = item['reviewed_at'].isoformat() if hasattr(item['reviewed_at'], 'isoformat') else item['reviewed_at']
            
            return self.json_response(paginated_data)
            
        except Exception as e:
            return self.error_response(f'Error fetching moderation queue: {str(e)}', 500)
    
    @admin_permission_required('moderate_content')
    @require_POST
    def post(self, request):
        """Take action on moderated content"""
        try:
            data = json.loads(request.body)
            moderation_id = data.get('moderation_id')
            action = data.get('action')  # approve, delete, flag, ignore
            reason = data.get('reason', '')
            
            moderation = ModeratedContent.objects.get(id=moderation_id)
            
            with transaction.atomic():
                if action == 'approve':
                    moderation.status = 'approved'
                    moderation.reviewed_by = request.admin_user
                    moderation.reviewed_at = timezone.now()
                    moderation.review_notes = reason or 'Content approved'
                    
                elif action == 'delete':
                    moderation.status = 'deleted'
                    moderation.reviewed_by = request.admin_user
                    moderation.reviewed_at = timezone.now()
                    moderation.review_notes = reason or 'Content deleted'
                    
                    # Delete the actual content
                    try:
                        if moderation.content_type == 'post':
                            Post.objects.get(id=moderation.object_id).delete()
                        elif moderation.content_type == 'comment':
                            Comment.objects.get(id=moderation.object_id).delete()
                    except (Post.DoesNotExist, Comment.DoesNotExist):
                        pass  # Content already deleted
                    
                elif action == 'flag':
                    moderation.status = 'flagged'
                    moderation.flagged_by = request.admin_user
                    moderation.flagged_at = timezone.now()
                    moderation.flag_reason = reason or 'Content flagged for review'
                    
                elif action == 'ignore':
                    moderation.status = 'ignored'
                    moderation.reviewed_by = request.admin_user
                    moderation.reviewed_at = timezone.now()
                    moderation.review_notes = reason or 'Content ignored'
                
                moderation.save()
                
                # Log the action
                AdminAction.objects.create(
                    admin=request.admin_user,
                    action_type=f'content_{action}',
                    severity='info' if action in ['approve', 'ignore'] else 'warning',
                    title=f'Content {action.title()}',
                    description=f'{action.title()} {moderation.content_type} (ID: {moderation.object_id}): {reason}',
                    metadata={
                        'moderation_id': str(moderation.id),
                        'content_type': moderation.content_type,
                        'content_id': moderation.object_id,
                        'action': action
                    }
                )
            
            return self.json_response({
                'message': f'Content {action}ed successfully',
                'moderation_id': moderation.id,
                'new_status': moderation.status
            })
            
        except ModeratedContent.DoesNotExist:
            return self.error_response('Moderation record not found', 404)
        except Exception as e:
            return self.error_response(f'Error processing moderation action: {str(e)}', 500)


# ================================
# Bulk Operations APIs
# ================================

class BulkActionsAPI(AdminAPIView):
    """API endpoint for bulk operations"""
    
    @admin_permission_required('manage_users')
    @require_POST
    def post(self, request):
        """Perform bulk actions on users or content"""
        try:
            data = json.loads(request.body)
            action_type = data.get('action_type')
            target_type = data.get('target_type')  # users, posts, comments
            target_ids = data.get('target_ids', [])
            params = data.get('params', {})
            
            if not target_ids:
                return self.error_response('No targets specified')
            
            results = {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            with transaction.atomic():
                if target_type == 'users':
                    results = self._bulk_user_actions(action_type, target_ids, params, request.admin_user)
                elif target_type == 'posts':
                    results = self._bulk_post_actions(action_type, target_ids, params, request.admin_user)
                elif target_type == 'moderation':
                    results = self._bulk_moderation_actions(action_type, target_ids, params, request.admin_user)
                else:
                    return self.error_response('Invalid target type')
                
                # Log bulk action
                AdminAction.objects.create(
                    admin=request.admin_user,
                    action_type='bulk_action',
                    severity='info',
                    title=f'Bulk {action_type} on {target_type}',
                    description=f'Performed {action_type} on {results["successful"]} {target_type}',
                    metadata={
                        'action_type': action_type,
                        'target_type': target_type,
                        'processed': results['processed'],
                        'successful': results['successful'],
                        'failed': results['failed']
                    }
                )
            
            return self.json_response(results)
            
        except Exception as e:
            return self.error_response(f'Error performing bulk action: {str(e)}', 500)
    
    def _bulk_user_actions(self, action_type: str, user_ids: List[int], params: Dict, admin_user: AdminUser) -> Dict:
        """Perform bulk actions on users"""
        results = {'processed': 0, 'successful': 0, 'failed': 0, 'errors': []}
        
        for user_id in user_ids:
            try:
                user = GupShupUser.objects.get(id=user_id)
                results['processed'] += 1
                
                if action_type == 'ban':
                    # Check if already banned
                    if not hasattr(user, 'ban_record') or not user.ban_record.is_active:
                        BannedUser.objects.create(
                            user=user,
                            admin=admin_user,
                            ban_type=params.get('ban_type', 'temporary'),
                            reason=params.get('reason', 'Bulk ban action'),
                            public_reason=params.get('public_reason', 'Terms violation'),
                            expires_at=timezone.now() + timedelta(days=int(params.get('duration', 7))) if params.get('ban_type') == 'temporary' else None
                        )
                        user.is_active = False
                        user.save()
                        results['successful'] += 1
                    else:
                        results['errors'].append(f'User {user.username} is already banned')
                        results['failed'] += 1
                
                elif action_type == 'warn':
                    UserWarning.objects.create(
                        user=user,
                        admin=admin_user,
                        warning_type=params.get('warning_type', 'general'),
                        severity=params.get('severity', 'medium'),
                        title=params.get('title', 'Bulk warning'),
                        message=params.get('message', 'This is a bulk warning message')
                    )
                    results['successful'] += 1
                
                elif action_type == 'activate':
                    user.is_active = True
                    user.save()
                    results['successful'] += 1
                
                elif action_type == 'deactivate':
                    user.is_active = False
                    user.save()
                    results['successful'] += 1
                
                else:
                    results['errors'].append(f'Unknown action type: {action_type}')
                    results['failed'] += 1
                    
            except GupShupUser.DoesNotExist:
                results['errors'].append(f'User with ID {user_id} not found')
                results['failed'] += 1
            except Exception as e:
                results['errors'].append(f'Error processing user {user_id}: {str(e)}')
                results['failed'] += 1
        
        return results
    
    def _bulk_post_actions(self, action_type: str, post_ids: List[int], params: Dict, admin_user: AdminUser) -> Dict:
        """Perform bulk actions on posts"""
        results = {'processed': 0, 'successful': 0, 'failed': 0, 'errors': []}
        
        for post_id in post_ids:
            try:
                post = Post.objects.get(id=post_id)
                results['processed'] += 1
                
                if action_type == 'delete':
                    post.delete()
                    results['successful'] += 1
                
                elif action_type == 'flag':
                    ModeratedContent.objects.update_or_create(
                        content_type='post',
                        object_id=post.id,
                        defaults={
                            'status': 'flagged',
                            'flagged_by': admin_user,
                            'flagged_at': timezone.now(),
                            'flag_reason': params.get('reason', 'Bulk flagged'),
                            'severity': params.get('severity', 'medium')
                        }
                    )
                    results['successful'] += 1
                
                else:
                    results['errors'].append(f'Unknown action type: {action_type}')
                    results['failed'] += 1
                    
            except Post.DoesNotExist:
                results['errors'].append(f'Post with ID {post_id} not found')
                results['failed'] += 1
            except Exception as e:
                results['errors'].append(f'Error processing post {post_id}: {str(e)}')
                results['failed'] += 1
        
        return results
    
    def _bulk_moderation_actions(self, action_type: str, moderation_ids: List[int], params: Dict, admin_user: AdminUser) -> Dict:
        """Perform bulk actions on moderation queue items"""
        results = {'processed': 0, 'successful': 0, 'failed': 0, 'errors': []}
        
        for mod_id in moderation_ids:
            try:
                moderation = ModeratedContent.objects.get(id=mod_id)
                results['processed'] += 1
                
                if action_type == 'approve':
                    moderation.status = 'approved'
                    moderation.reviewed_by = admin_user
                    moderation.reviewed_at = timezone.now()
                    moderation.review_notes = params.get('reason', 'Bulk approved')
                    
                elif action_type == 'delete':
                    moderation.status = 'deleted'
                    moderation.reviewed_by = admin_user
                    moderation.reviewed_at = timezone.now()
                    moderation.review_notes = params.get('reason', 'Bulk deleted')
                    
                    # Delete actual content
                    try:
                        if moderation.content_type == 'post':
                            Post.objects.get(id=moderation.object_id).delete()
                        elif moderation.content_type == 'comment':
                            Comment.objects.get(id=moderation.object_id).delete()
                    except (Post.DoesNotExist, Comment.DoesNotExist):
                        pass
                
                elif action_type == 'ignore':
                    moderation.status = 'ignored'
                    moderation.reviewed_by = admin_user
                    moderation.reviewed_at = timezone.now()
                    moderation.review_notes = params.get('reason', 'Bulk ignored')
                
                moderation.save()
                results['successful'] += 1
                    
            except ModeratedContent.DoesNotExist:
                results['errors'].append(f'Moderation record with ID {mod_id} not found')
                results['failed'] += 1
            except Exception as e:
                results['errors'].append(f'Error processing moderation {mod_id}: {str(e)}')
                results['failed'] += 1
        
        return results


# ================================
# Export APIs
# ================================

class ExportDataAPI(AdminAPIView):
    """API endpoint for data export"""
    
    @admin_permission_required('view_reports')
    def get(self, request):
        """Export data in various formats"""
        try:
            export_type = request.GET.get('type', 'analytics')
            format_type = request.GET.get('format', 'json')
            days = int(request.GET.get('days', 30))
            
            report_generator = ReportGenerator()
            
            if export_type == 'analytics':
                data = report_generator.generate_comprehensive_report(days)
            elif export_type == 'users':
                data = self._export_users_data()
            elif export_type == 'content':
                data = self._export_content_data(days)
            elif export_type == 'moderation':
                data = self._export_moderation_data(days)
            else:
                return self.error_response('Invalid export type')
            
            if format_type == 'csv':
                return report_generator.export_to_csv(data)
            elif format_type == 'json':
                return report_generator.export_to_json(data)
            else:
                return self.error_response('Invalid format type')
                
        except Exception as e:
            return self.error_response(f'Error exporting data: {str(e)}', 500)
    
    def _export_users_data(self) -> Dict:
        """Export users data for CSV/JSON"""
        users = GupShupUser.objects.select_related().annotate(
            posts_count=Count('posts'),
            warnings_count=Count('warnings')
        ).values(
            'id', 'username', 'email', 'first_name', 'last_name',
            'city', 'state', 'is_active', 'is_verified', 'date_joined',
            'posts_count', 'warnings_count'
        )
        
        return {
            'export_type': 'users',
            'export_timestamp': timezone.now().isoformat(),
            'total_records': len(users),
            'data': list(users)
        }
    
    def _export_content_data(self, days: int) -> Dict:
        """Export content data for CSV/JSON"""
        start_date = timezone.now() - timedelta(days=days)
        
        posts = Post.objects.filter(created_at__gte=start_date).select_related('author').values(
            'id', 'content', 'author__username', 'created_at',
            'likes_count', 'comments_count', 'privacy'
        )
        
        return {
            'export_type': 'content',
            'export_timestamp': timezone.now().isoformat(),
            'period_days': days,
            'total_records': len(posts),
            'data': list(posts)
        }
    
    def _export_moderation_data(self, days: int) -> Dict:
        """Export moderation data for CSV/JSON"""
        start_date = timezone.now() - timedelta(days=days)
        
        moderation_data = ModeratedContent.objects.filter(
            flagged_at__gte=start_date
        ).select_related('flagged_by', 'reviewed_by').values(
            'id', 'content_type', 'object_id', 'status', 'severity',
            'flag_reason', 'flagged_by__username', 'flagged_at',
            'reviewed_by__username', 'reviewed_at', 'review_notes'
        )
        
        return {
            'export_type': 'moderation',
            'export_timestamp': timezone.now().isoformat(),
            'period_days': days,
            'total_records': len(moderation_data),
            'data': list(moderation_data)
        }


# ================================
# Real-time Updates API
# ================================

class LiveUpdatesAPI(AdminAPIView):
    """API endpoint for real-time updates"""
    
    def get(self, request):
        """Get live updates for dashboard"""
        try:
            last_update = request.GET.get('last_update')
            
            updates = {
                'timestamp': timezone.now().isoformat(),
                'notifications': [],
                'stats_updates': {},
                'alerts': []
            }
            
            # Get recent notifications
            if last_update:
                try:
                    last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    
                    # Recent admin actions
                    recent_actions = AdminAction.objects.filter(
                        created_at__gt=last_update_dt
                    ).order_by('-created_at')[:10]
                    
                    for action in recent_actions:
                        updates['notifications'].append({
                            'type': 'admin_action',
                            'message': f'{action.admin.username if action.admin else "System"}: {action.title}',
                            'severity': action.severity,
                            'timestamp': action.created_at.isoformat()
                        })
                    
                    # Critical moderation items
                    critical_moderation = ModeratedContent.objects.filter(
                        flagged_at__gt=last_update_dt,
                        severity='critical',
                        status='pending'
                    ).count()
                    
                    if critical_moderation > 0:
                        updates['alerts'].append({
                            'type': 'critical_moderation',
                            'message': f'{critical_moderation} critical items need immediate attention',
                            'action_url': '/admin-panel/moderation-queue/?severity=critical'
                        })
                        
                except ValueError:
                    pass  # Invalid date format
            
            # Always include current stats
            updates['stats_updates'] = {
                'pending_moderation': ModeratedContent.objects.filter(status='pending').count(),
                'active_warnings': UserWarning.objects.filter(status='active').count(),
                'online_users': self._get_online_users_count(),
                'active_admins': AdminSession.objects.filter(
                    is_active=True,
                    expires_at__gt=timezone.now()
                ).count()
            }
            
            return self.json_response(updates)
            
        except Exception as e:
            return self.error_response(f'Error fetching live updates: {str(e)}', 500)
    
    def _get_online_users_count(self) -> int:
        """Get count of users online in the last 15 minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=15)
        return GupShupUser.objects.filter(
            last_login__gte=cutoff_time,
            is_active=True
        ).count()


# ================================
# Webhook API for automation
# ================================

@csrf_exempt
@require_POST
def automation_webhook(request):
    """Webhook endpoint for automated moderation triggers"""
    try:
        # Verify webhook signature (implement based on your needs)
        # signature = request.META.get('HTTP_X_SIGNATURE')
        # if not verify_webhook_signature(request.body, signature):
        #     return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        data = json.loads(request.body)
        event_type = data.get('event_type')
        
        if event_type == 'content_reported':
            # Auto-flag reported content
            content_type = data.get('content_type')
            content_id = data.get('content_id')
            report_reason = data.get('reason', 'User reported content')
            
            ModeratedContent.objects.update_or_create(
                content_type=content_type,
                object_id=content_id,
                defaults={
                    'status': 'flagged',
                    'flag_reason': report_reason,
                    'severity': 'medium',
                    'auto_flagged': True,
                    'flagged_at': timezone.now(),
                    'notes': 'Auto-flagged via webhook'
                }
            )
            
        elif event_type == 'spam_detected':
            # Auto-flag spam content
            content_type = data.get('content_type')
            content_id = data.get('content_id')
            confidence = data.get('confidence', 0.5)
            
            severity = 'high' if confidence > 0.8 else 'medium'
            
            ModeratedContent.objects.update_or_create(
                content_type=content_type,
                object_id=content_id,
                defaults={
                    'status': 'flagged',
                    'flag_reason': f'Spam detected (confidence: {confidence})',
                    'severity': severity,
                    'auto_flagged': True,
                    'flagged_at': timezone.now(),
                    'notes': f'Auto-flagged by spam detection system (confidence: {confidence})'
                }
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Webhook processed: {event_type}',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)