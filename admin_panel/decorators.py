"""
Admin Panel Decorators for Authentication, Permission, and Logging

This module provides decorators for securing admin views and logging admin actions.
"""

from functools import wraps
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from .auth import AdminSessionManager
from .models import AdminAction


def admin_required(view_func=None, *, login_url='admin_panel:login', message=None):
    """
    Decorator to ensure admin authentication is required for a view.
    
    Usage:
        @admin_required
        def my_view(request):
            # request.admin_user will be available
            pass
        
        @admin_required(login_url='custom:login', message='Custom message')
        def my_view(request):
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            session_manager = AdminSessionManager()
            
            if not session_manager.is_admin_authenticated(request):
                if message:
                    messages.warning(request, message)
                return redirect(login_url)
            
            # Attach admin user to request for easy access
            request.admin_user = session_manager.get_admin_from_session(request)
            
            # Double-check admin is valid (security measure)
            if not request.admin_user:
                return redirect(login_url)
            
            return func(request, *args, **kwargs)
        return wrapper
    
    # Handle decorator being called with or without arguments
    if view_func is None:
        return decorator
    else:
        return decorator(view_func)


def admin_permission_required(permission, message=None):
    """
    Decorator to check specific admin permission.
    
    Args:
        permission (str): Permission name to check (e.g., 'manage_users')
        message (str): Custom error message
    
    Usage:
        @admin_permission_required('manage_users')
        def ban_user(request):
            pass
            
        @admin_permission_required('delete_posts', 'You cannot delete posts')
        def delete_post(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            session_manager = AdminSessionManager()
            
            if not session_manager.is_admin_authenticated(request):
                return redirect('admin_panel:login')
            
            admin_user = session_manager.get_admin_from_session(request)
            
            if not admin_user:
                return redirect('admin_panel:login')
            
            # Check permission
            if not admin_user.has_permission(permission):
                error_message = message or f'You do not have permission to {permission}. Contact your administrator.'
                
                # Return JSON for AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    }, status=403)
                
                # Log unauthorized access attempt
                AdminAction.objects.create(
                    admin=admin_user,
                    action_type='unauthorized_access',
                    severity='warning',
                    title='Unauthorized access attempt',
                    description=f'Admin {admin_user.username} tried to access {request.path} without {permission} permission',
                    ip_address=session_manager._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    request_path=request.path,
                    request_method=request.method,
                    status='failed'
                )
                
                messages.error(request, error_message)
                return HttpResponseForbidden(error_message)
            
            # Attach admin user to request
            request.admin_user = admin_user
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_role_required(role, message=None):
    """
    Decorator to check admin role requirement.
    
    Args:
        role (str): Required role ('super_admin', 'admin', 'moderator', 'analyst')
        message (str): Custom error message
    
    Usage:
        @admin_role_required('super_admin')
        def system_settings(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            session_manager = AdminSessionManager()
            
            if not session_manager.is_admin_authenticated(request):
                return redirect('admin_panel:login')
            
            admin_user = session_manager.get_admin_from_session(request)
            
            if not admin_user:
                return redirect('admin_panel:login')
            
            # Check role (super admin bypasses all role checks)
            if not admin_user.is_super_admin() and admin_user.role != role:
                error_message = message or f'You need {role} role to access this resource.'
                
                # Return JSON for AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    }, status=403)
                
                # Log unauthorized role access
                AdminAction.objects.create(
                    admin=admin_user,
                    action_type='unauthorized_access',
                    severity='warning',
                    title='Role access denied',
                    description=f'Admin {admin_user.username} ({admin_user.role}) tried to access {role}-only resource: {request.path}',
                    ip_address=session_manager._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    request_path=request.path,
                    request_method=request.method,
                    status='failed'
                )
                
                messages.error(request, error_message)
                return HttpResponseForbidden(error_message)
            
            # Attach admin user to request
            request.admin_user = admin_user
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def log_admin_action(action_type, description=None, severity='info', target_field=None):
    """
    Decorator to automatically log admin actions.
    
    Args:
        action_type (str): Type of action being performed
        description (str): Custom description (optional)
        severity (str): Action severity ('info', 'warning', 'error', 'critical')
        target_field (str): Request field containing target object info
    
    Usage:
        @log_admin_action('user_banned', 'User was banned for policy violation')
        def ban_user(request):
            pass
            
        @log_admin_action('post_deleted', target_field='post_id')
        def delete_post(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = timezone.now()
            
            # Execute the view
            try:
                response = view_func(request, *args, **kwargs)
                status = 'success'
                error_details = None
            except Exception as e:
                status = 'failed'
                error_details = str(e)
                raise  # Re-raise the exception
            finally:
                # Log the action if admin is authenticated
                if hasattr(request, 'admin_user') and request.admin_user:
                    session_manager = AdminSessionManager()
                    
                    # Determine success/failure based on response
                    if 'response' in locals() and hasattr(response, 'status_code'):
                        if response.status_code >= 400:
                            status = 'failed'
                    
                    # Create action description
                    if description:
                        action_description = description
                    else:
                        action_description = f'Admin performed {action_type}'
                    
                    # Extract target information if specified
                    metadata = {
                        'execution_time_ms': int((timezone.now() - start_time).total_seconds() * 1000),
                        'view_name': view_func.__name__
                    }
                    
                    if target_field and target_field in request.POST:
                        metadata['target_id'] = request.POST[target_field]
                    elif target_field and target_field in request.GET:
                        metadata['target_id'] = request.GET[target_field]
                    
                    if error_details:
                        metadata['error'] = error_details
                    
                    # Create admin action log
                    AdminAction.objects.create(
                        admin=request.admin_user,
                        action_type=action_type,
                        severity=severity,
                        title=f'Admin {action_type}',
                        description=action_description,
                        ip_address=session_manager._get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        request_path=request.path,
                        request_method=request.method,
                        status=status,
                        metadata=metadata
                    )
            
            return response
        return wrapper
    return decorator


def rate_limit(requests_per_minute=60, per_user=True):
    """
    Rate limiting decorator for admin actions.
    
    Args:
        requests_per_minute (int): Maximum requests per minute
        per_user (bool): Rate limit per user or globally
    
    Usage:
        @rate_limit(30)  # 30 requests per minute per user
        def bulk_delete(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            import time
            
            if not hasattr(request, 'admin_user'):
                return view_func(request, *args, **kwargs)
            
            # Create cache key
            if per_user:
                cache_key = f'admin_rate_limit_{request.admin_user.id}_{view_func.__name__}'
            else:
                cache_key = f'admin_rate_limit_global_{view_func.__name__}'
            
            # Get current request count
            current_time = int(time.time())
            minute_key = f'{cache_key}_{current_time // 60}'
            
            request_count = cache.get(minute_key, 0)
            
            if request_count >= requests_per_minute:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Rate limit exceeded. Please wait before trying again.'
                    }, status=429)
                
                messages.error(request, 'Too many requests. Please wait before trying again.')
                return HttpResponseForbidden('Rate limit exceeded')
            
            # Increment counter
            cache.set(minute_key, request_count + 1, 60)  # Expire after 60 seconds
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def ajax_required(view_func):
    """
    Decorator to ensure the request is AJAX.
    
    Usage:
        @ajax_required
        def api_endpoint(request):
            return JsonResponse({'success': True})
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'This endpoint requires an AJAX request'
            }, status=400)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def post_required(view_func):
    """
    Decorator to ensure the request method is POST.
    
    Usage:
        @post_required
        def delete_user(request):
            pass
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method != 'POST':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'This endpoint requires POST method'
                }, status=405)
            
            messages.error(request, 'Invalid request method.')
            return HttpResponseForbidden('POST method required')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def super_admin_required(view_func):
    """
    Convenience decorator for super admin only views.
    
    Usage:
        @super_admin_required
        def system_maintenance(request):
            pass
    """
    return admin_role_required('super_admin')(view_func)


# Legacy decorator names for backward compatibility
require_admin_permission = admin_permission_required
require_admin_role = admin_role_required