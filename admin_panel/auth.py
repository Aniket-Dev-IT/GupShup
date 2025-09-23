from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import secrets
import json
from datetime import timedelta
from .models import AdminUser, AdminSession, AdminAction

User = lambda: None  # Placeholder since we don't need regular User model here


class AdminAuthenticationBackend:
    """
    Enhanced authentication backend for admin users with security features
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate admin user with enhanced security
        """
        if not username or not password:
            return None
            
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check rate limiting
        if self._is_rate_limited(ip_address, username):
            self._log_failed_attempt(None, username, 'Rate limited', ip_address, user_agent)
            return None
        
        try:
            # Get admin user
            admin_user = AdminUser.objects.get(
                username=username,
                status='active',
                is_active=True
            )
            
            # Check if account is locked
            if admin_user.is_locked():
                self._log_failed_attempt(admin_user, username, 'Account locked', ip_address, user_agent)
                return None
            
            # Check IP restrictions
            if not admin_user.is_ip_allowed(ip_address):
                self._log_failed_attempt(admin_user, username, 'IP not allowed', ip_address, user_agent)
                return None
            
            # Check password
            if admin_user.check_password(password):
                # Reset failed attempts on successful login
                admin_user.reset_failed_login()
                
                # Update login info
                admin_user.last_login = timezone.now()
                admin_user.last_login_ip = ip_address
                admin_user.login_count += 1
                admin_user.save(update_fields=[
                    'last_login', 'last_login_ip', 'login_count'
                ])
                
                # Log successful login
                self._log_action(
                    admin_user, 'login', 'success',
                    f'Admin {username} logged in successfully',
                    ip_address, user_agent, request
                )
                
                # Clear rate limiting
                self._clear_rate_limit(ip_address, username)
                
                return admin_user
            else:
                # Increment failed attempts
                admin_user.increment_failed_login()
                self._increment_rate_limit(ip_address, username)
                
                self._log_failed_attempt(
                    admin_user, username, 'Invalid password', 
                    ip_address, user_agent
                )
                
        except AdminUser.DoesNotExist:
            # Increment rate limiting for unknown users
            self._increment_rate_limit(ip_address, username)
            
            self._log_failed_attempt(
                None, username, 'User not found', 
                ip_address, user_agent
            )
        
        return None
    
    def _is_rate_limited(self, ip_address, username):
        """Check if IP/username is rate limited"""
        ip_key = f'admin_login_attempts_ip_{ip_address}'
        user_key = f'admin_login_attempts_user_{username}'
        
        ip_attempts = cache.get(ip_key, 0)
        user_attempts = cache.get(user_key, 0)
        
        return ip_attempts >= 10 or user_attempts >= 5  # Configurable limits
    
    def _increment_rate_limit(self, ip_address, username):
        """Increment rate limiting counters"""
        ip_key = f'admin_login_attempts_ip_{ip_address}'
        user_key = f'admin_login_attempts_user_{username}'
        
        # Increment with 1 hour expiry
        cache.set(ip_key, cache.get(ip_key, 0) + 1, 3600)
        cache.set(user_key, cache.get(user_key, 0) + 1, 3600)
    
    def _clear_rate_limit(self, ip_address, username):
        """Clear rate limiting on successful login"""
        ip_key = f'admin_login_attempts_ip_{ip_address}'
        user_key = f'admin_login_attempts_user_{username}'
        
        cache.delete(ip_key)
        cache.delete(user_key)
    
    def _log_failed_attempt(self, admin_user, username, reason, ip_address, user_agent):
        """Log failed login attempt"""
        AdminAction.objects.create(
            admin=admin_user,
            action_type='failed_login',
            severity='warning',
            title=f'Failed login: {username}',
            description=f'Failed login attempt for {username}: {reason}',
            ip_address=ip_address,
            user_agent=user_agent,
            status='failed',
            metadata={'reason': reason, 'username': username}
        )
    
    def _log_action(self, admin_user, action_type, status, description, ip_address, user_agent, request):
        """Log admin action"""
        AdminAction.objects.create(
            admin=admin_user,
            action_type=action_type,
            severity='info',
            title=f'Admin {action_type}',
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request.path if request else '',
            request_method=request.method if request else '',
            status=status
        )
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AdminSessionManager:
    """
    Enhanced session management with security features
    """
    
    def login(self, request, admin_user):
        """Create secure admin session"""
        # Cleanup old sessions for this admin
        self._cleanup_old_sessions(admin_user)
        
        # Generate secure session key
        session_key = self._generate_session_key()
        
        # Get location info (you can integrate with IP geolocation service)
        ip_address = self._get_client_ip(request)
        country, city = self._get_location_from_ip(ip_address)
        
        # Create session record
        session = AdminSession.objects.create(
            admin=admin_user,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            expires_at=timezone.now() + admin_user.get_session_timeout(),
            country=country,
            city=city
        )
        
        # Store in Django session
        request.session['admin_user_id'] = str(admin_user.id)
        request.session['admin_session_key'] = session_key
        request.session['admin_login_time'] = timezone.now().isoformat()
        
        # Set session expiry
        request.session.set_expiry(admin_user.session_timeout_minutes * 60)
        
        return session
    
    def logout(self, request, admin_user=None):
        """Secure logout with comprehensive cleanup"""
        session_key = request.session.get('admin_session_key')
        
        # Get admin user if not provided
        if not admin_user:
            admin_user = self.get_admin_from_session(request)
        
        # Deactivate session record
        if session_key:
            AdminSession.objects.filter(
                session_key=session_key
            ).update(is_active=False)
        
        # Log logout
        if admin_user:
            AdminAction.objects.create(
                admin=admin_user,
                action_type='logout',
                severity='info',
                title='Admin logout',
                description=f'Admin {admin_user.username} logged out',
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.path,
                request_method=request.method
            )
        
        # Clear Django session completely
        request.session.flush()
    
    def is_admin_authenticated(self, request):
        """Enhanced authentication check"""
        admin_user_id = request.session.get('admin_user_id')
        session_key = request.session.get('admin_session_key')
        
        if not admin_user_id or not session_key:
            return False
        
        try:
            # Get session and admin user
            session = AdminSession.objects.select_related('admin').get(
                session_key=session_key,
                admin_id=admin_user_id,
                is_active=True
            )
            
            # Check if session is expired
            if session.is_expired():
                session.is_active = False
                session.save()
                return False
            
            # Check if admin is still active
            if not session.admin.is_active or session.admin.status != 'active':
                session.is_active = False
                session.save()
                return False
            
            # Check IP consistency (optional security measure)
            current_ip = self._get_client_ip(request)
            if getattr(settings, 'ADMIN_CHECK_IP_CONSISTENCY', False):
                if session.ip_address != current_ip:
                    # Log suspicious activity
                    AdminAction.objects.create(
                        admin=session.admin,
                        action_type='suspicious_activity',
                        severity='warning',
                        title='IP address changed during session',
                        description=f'Session IP changed from {session.ip_address} to {current_ip}',
                        ip_address=current_ip,
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    
                    # Optionally terminate session
                    if getattr(settings, 'ADMIN_TERMINATE_ON_IP_CHANGE', True):
                        session.is_active = False
                        session.save()
                        return False
            
            # Update last activity
            session.last_activity = timezone.now()
            session.save(update_fields=['last_activity'])
            
            return True
            
        except AdminSession.DoesNotExist:
            return False
    
    def get_admin_from_session(self, request):
        """Get admin user from session with validation"""
        if not self.is_admin_authenticated(request):
            return None
        
        admin_user_id = request.session.get('admin_user_id')
        try:
            return AdminUser.objects.get(
                id=admin_user_id, 
                is_active=True, 
                status='active'
            )
        except AdminUser.DoesNotExist:
            return None
    
    def _cleanup_old_sessions(self, admin_user):
        """Clean up old/expired sessions for admin"""
        # Deactivate expired sessions
        AdminSession.objects.filter(
            admin=admin_user,
            expires_at__lt=timezone.now(),
            is_active=True
        ).update(is_active=False)
        
        # Limit concurrent sessions (keep only latest 3)
        active_sessions = AdminSession.objects.filter(
            admin=admin_user,
            is_active=True
        ).order_by('-created_at')
        
        if active_sessions.count() > 2:  # Allow max 3 concurrent sessions
            old_sessions = active_sessions[2:]
            for session in old_sessions:
                session.is_active = False
                session.save()
    
    def _generate_session_key(self):
        """Generate cryptographically secure session key"""
        return secrets.token_urlsafe(32)
    
    def _get_client_ip(self, request):
        """Get client IP with proxy support"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_location_from_ip(self, ip_address):
        """Get location from IP (integrate with geolocation service)"""
        # This is a placeholder - integrate with a real geolocation service
        # like MaxMind GeoIP, IPStack, etc.
        return 'India', 'Unknown'  # Default values



# Enhanced decorator functions

def admin_required(view_func):
    """
    Basic admin authentication decorator
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        session_manager = AdminSessionManager()
        
        if not session_manager.is_admin_authenticated(request):
            return redirect('admin_panel:login')
        
        # Attach admin user to request
        request.admin_user = session_manager.get_admin_from_session(request)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_permission_required(permission):
    """
    Decorator to check specific admin permission
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
                return HttpResponseForbidden(
                    f'You do not have permission to {permission}. Contact your administrator.'
                )
            
            # Attach admin user to request
            request.admin_user = admin_user
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_role_required(role):
    """
    Decorator to check admin role
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
                return HttpResponseForbidden(
                    f'You need {role} role to access this resource.'
                )
            
            # Attach admin user to request
            request.admin_user = admin_user
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def log_admin_action(action_type, description=None, severity='info'):
    """
    Decorator to automatically log admin actions
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Execute the view
            response = view_func(request, *args, **kwargs)
            
            # Log the action if admin is authenticated
            if hasattr(request, 'admin_user') and request.admin_user:
                # Determine success/failure based on response
                status = 'success'
                if hasattr(response, 'status_code') and response.status_code >= 400:
                    status = 'failed'
                
                # Create action description if not provided
                action_description = description or f'Admin performed {action_type}'
                
                AdminAction.objects.create(
                    admin=request.admin_user,
                    action_type=action_type,
                    severity=severity,
                    title=f'Admin {action_type}',
                    description=action_description,
                    ip_address=AdminSessionManager()._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    request_path=request.path,
                    request_method=request.method,
                    status=status
                )
            
            return response
        return wrapper
    return decorator


# Utility functions

def hash_admin_password(password):
    """Hash admin password using Django's password hashing"""
    return make_password(password)


def verify_admin_password(password, hashed_password):
    """Verify admin password against hash"""
    return check_password(password, hashed_password)


def create_admin_user(username, email, password, first_name='', last_name='', 
                     role='admin', created_by=None, **permissions):
    """Create a new admin user with proper password hashing"""
    
    # Check if username already exists
    if AdminUser.objects.filter(username=username).exists():
        raise ValueError(f'Admin user with username {username} already exists')
    
    # Check if email already exists
    if AdminUser.objects.filter(email=email).exists():
        raise ValueError(f'Admin user with email {email} already exists')
    
    # Create admin user using the manager
    admin_user = AdminUser.objects.create_admin(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=role,
        created_by=created_by,
        **permissions
    )
    
    return admin_user


# Legacy decorator names for backward compatibility
require_admin_permission = admin_permission_required
require_admin_role = admin_role_required
