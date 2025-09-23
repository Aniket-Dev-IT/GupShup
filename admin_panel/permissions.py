"""
Admin Panel Permissions and Role-Based Access Control

This module defines permissions for different admin roles and provides
decorators and utility functions for access control.
"""

from functools import wraps
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import AdminUser
from .audit import audit_log


# Permission levels
class PermissionLevel:
    """Permission level constants"""
    READ = 'read'
    WRITE = 'write'
    DELETE = 'delete'
    ADMIN = 'admin'


# Role-based permissions matrix
ROLE_PERMISSIONS = {
    'super_admin': {
        'users': ['read', 'write', 'delete', 'admin'],
        'posts': ['read', 'write', 'delete', 'admin'],
        'moderation': ['read', 'write', 'delete', 'admin'],
        'reports': ['read', 'write', 'delete', 'admin'],
        'settings': ['read', 'write', 'delete', 'admin'],
        'audit': ['read', 'write', 'delete', 'admin'],
        'security': ['read', 'write', 'delete', 'admin'],
        'system': ['read', 'write', 'delete', 'admin'],
        'bulk_actions': ['read', 'write', 'delete', 'admin'],
    },
    'admin': {
        'users': ['read', 'write', 'delete'],
        'posts': ['read', 'write', 'delete'],
        'moderation': ['read', 'write', 'delete'],
        'reports': ['read', 'write'],
        'settings': ['read', 'write'],
        'audit': ['read'],
        'security': ['read'],
        'system': ['read'],
        'bulk_actions': ['read', 'write'],
    },
    'moderator': {
        'users': ['read', 'write'],
        'posts': ['read', 'write', 'delete'],
        'moderation': ['read', 'write', 'delete'],
        'reports': ['read'],
        'settings': ['read'],
        'audit': [],
        'security': [],
        'system': ['read'],
        'bulk_actions': ['read'],
    },
}


def get_user_permissions(user):
    """
    Get all permissions for a user based on their role
    
    Args:
        user: AdminUser instance
        
    Returns:
        dict: Dictionary of permissions by module
    """
    if not isinstance(user, AdminUser) or not user.is_active:
        return {}
    
    return ROLE_PERMISSIONS.get(user.role, {})


def has_permission(user, module, permission_level):
    """
    Check if user has specific permission for a module
    
    Args:
        user: AdminUser instance
        module: str - module name (e.g., 'users', 'posts')
        permission_level: str - permission level ('read', 'write', 'delete', 'admin')
        
    Returns:
        bool: True if user has permission
    """
    user_permissions = get_user_permissions(user)
    module_permissions = user_permissions.get(module, [])
    return permission_level in module_permissions


def require_permission(module, permission_level, ajax=False):
    """
    Decorator to require specific permission for a view
    
    Args:
        module: str - module name
        permission_level: str - required permission level
        ajax: bool - if True, return JSON response for AJAX requests
        
    Usage:
        @require_permission('users', 'write')
        def ban_user_view(request):
            # View code here
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated admin
            if not hasattr(request, 'admin_user') or not request.admin_user:
                if ajax or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Authentication required'
                    }, status=401)
                return redirect(reverse('admin_panel:login'))
            
            # Check permissions
            if not has_permission(request.admin_user, module, permission_level):
                # Log unauthorized access attempt
                audit_log(
                    admin_user=request.admin_user,
                    action=f'unauthorized_access_attempt',
                    target_type='permission',
                    metadata={
                        'module': module,
                        'permission_level': permission_level,
                        'view': view_func.__name__,
                        'url': request.get_full_path(),
                        'method': request.method,
                    },
                    severity='high'
                )
                
                if ajax or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Insufficient permissions'
                    }, status=403)
                
                messages.error(request, 'You do not have permission to perform this action.')
                return redirect(reverse('admin_panel:dashboard'))
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(required_roles, ajax=False):
    """
    Decorator to require specific admin roles
    
    Args:
        required_roles: str or list - required role(s)
        ajax: bool - if True, return JSON response for AJAX requests
        
    Usage:
        @require_role(['super_admin', 'admin'])
        def sensitive_view(request):
            # View code here
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated admin
            if not hasattr(request, 'admin_user') or not request.admin_user:
                if ajax or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Authentication required'
                    }, status=401)
                return redirect(reverse('admin_panel:login'))
            
            # Check role
            if request.admin_user.role not in required_roles:
                # Log unauthorized access attempt
                audit_log(
                    admin_user=request.admin_user,
                    action=f'unauthorized_role_access',
                    target_type='role',
                    metadata={
                        'required_roles': required_roles,
                        'user_role': request.admin_user.role,
                        'view': view_func.__name__,
                        'url': request.get_full_path(),
                        'method': request.method,
                    },
                    severity='high'
                )
                
                if ajax or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Insufficient role permissions'
                    }, status=403)
                
                messages.error(request, 'Your role does not have access to this resource.')
                return redirect(reverse('admin_panel:dashboard'))
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class PermissionMixin:
    """
    Mixin for class-based views to add permission checking
    """
    required_permission = None
    required_permission_level = 'read'
    required_roles = None
    
    def dispatch(self, request, *args, **kwargs):
        # Check authentication
        if not hasattr(request, 'admin_user') or not request.admin_user:
            return redirect(reverse('admin_panel:login'))
        
        # Check role if specified
        if self.required_roles:
            required_roles = self.required_roles
            if isinstance(required_roles, str):
                required_roles = [required_roles]
            
            if request.admin_user.role not in required_roles:
                raise PermissionDenied("Insufficient role permissions")
        
        # Check permission if specified
        if self.required_permission:
            if not has_permission(request.admin_user, self.required_permission, self.required_permission_level):
                raise PermissionDenied("Insufficient permissions")
        
        return super().dispatch(request, *args, **kwargs)


def check_bulk_action_permission(admin_user, action_type, target_count=1):
    """
    Check if admin user can perform bulk actions
    
    Args:
        admin_user: AdminUser instance
        action_type: str - type of bulk action ('delete', 'ban', etc.)
        target_count: int - number of targets for the action
        
    Returns:
        dict: {'allowed': bool, 'reason': str}
    """
    # Super admins can do anything
    if admin_user.role == 'super_admin':
        return {'allowed': True, 'reason': 'Super admin privileges'}
    
    # Check bulk action permissions
    if not has_permission(admin_user, 'bulk_actions', 'write'):
        return {'allowed': False, 'reason': 'No bulk action permissions'}
    
    # Admins have limits on bulk actions
    if admin_user.role == 'admin':
        if action_type in ['delete', 'ban'] and target_count > 100:
            return {'allowed': False, 'reason': 'Bulk action limit exceeded (max 100)'}
    
    # Moderators have strict limits
    elif admin_user.role == 'moderator':
        if action_type in ['delete', 'ban']:
            return {'allowed': False, 'reason': 'Moderators cannot perform bulk delete/ban actions'}
        if target_count > 20:
            return {'allowed': False, 'reason': 'Bulk action limit exceeded (max 20)'}
    
    return {'allowed': True, 'reason': 'Permission granted'}


def get_accessible_modules(admin_user):
    """
    Get list of modules accessible to admin user
    
    Args:
        admin_user: AdminUser instance
        
    Returns:
        list: List of accessible module names
    """
    permissions = get_user_permissions(admin_user)
    return list(permissions.keys())


def get_permission_summary(admin_user):
    """
    Get summary of admin user permissions for display
    
    Args:
        admin_user: AdminUser instance
        
    Returns:
        dict: Detailed permission summary
    """
    permissions = get_user_permissions(admin_user)
    
    summary = {
        'role': admin_user.role,
        'modules': {},
        'capabilities': []
    }
    
    for module, perms in permissions.items():
        summary['modules'][module] = {
            'read': 'read' in perms,
            'write': 'write' in perms,
            'delete': 'delete' in perms,
            'admin': 'admin' in perms,
        }
    
    # Add capability flags
    if has_permission(admin_user, 'bulk_actions', 'write'):
        summary['capabilities'].append('bulk_actions')
    if has_permission(admin_user, 'system', 'admin'):
        summary['capabilities'].append('system_admin')
    if has_permission(admin_user, 'security', 'admin'):
        summary['capabilities'].append('security_admin')
    
    return summary


# Middleware to add admin_user to request
class AdminAuthMiddleware:
    """
    Middleware to add authenticated admin user to request object
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Add admin_user to request if session contains admin info
        request.admin_user = None
        
        if 'admin_user_id' in request.session:
            try:
                admin_user = AdminUser.objects.get(
                    id=request.session['admin_user_id'],
                    is_active=True
                )
                
                # Validate session security
                session_ip = request.session.get('admin_ip')
                session_ua = request.session.get('admin_user_agent')
                current_ip = request.META.get('REMOTE_ADDR')
                current_ua = request.META.get('HTTP_USER_AGENT')
                
                # Basic session validation
                if session_ip == current_ip and session_ua == current_ua:
                    request.admin_user = admin_user
                else:
                    # Session security violation
                    request.session.flush()
                    audit_log(
                        admin_user=admin_user,
                        action='session_security_violation',
                        metadata={
                            'expected_ip': session_ip,
                            'actual_ip': current_ip,
                            'expected_ua': session_ua,
                            'actual_ua': current_ua,
                        },
                        severity='high'
                    )
            
            except AdminUser.DoesNotExist:
                # Clean up invalid session
                if 'admin_user_id' in request.session:
                    del request.session['admin_user_id']
        
        response = self.get_response(request)
        return response


# Context processor for templates
def admin_permissions_context(request):
    """
    Context processor to add permission info to templates
    """
    if hasattr(request, 'admin_user') and request.admin_user:
        return {
            'admin_permissions': get_permission_summary(request.admin_user),
            'admin_user': request.admin_user,
        }
    return {}