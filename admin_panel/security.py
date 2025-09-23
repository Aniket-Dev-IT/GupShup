"""
GupShup Admin Panel Security Module

This module provides comprehensive security features for the admin panel including
IP whitelist/blacklist management, rate limiting, CSRF enhancements, session security,
and encryption for sensitive data.
"""

import hashlib
import hmac
import secrets
import ipaddress
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from functools import wraps
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.db import models, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.middleware.csrf import get_token

from .models import AdminUser, AdminSession, AdminAction


class SecurityConfig:
    """Security configuration and constants"""
    
    # Rate limiting settings
    DEFAULT_RATE_LIMIT = 60  # requests per minute
    STRICT_RATE_LIMIT = 10   # requests per minute for sensitive actions
    LOGIN_RATE_LIMIT = 5     # login attempts per 15 minutes
    
    # Session security
    SESSION_TIMEOUT_MINUTES = 480  # 8 hours
    MAX_CONCURRENT_SESSIONS = 3
    SESSION_IP_CHECK = True
    SESSION_USER_AGENT_CHECK = False  # Less strict
    
    # IP security
    MAX_FAILED_ATTEMPTS = 5
    IP_LOCKOUT_DURATION = 3600  # 1 hour in seconds
    
    # Encryption
    ENCRYPTION_KEY_ROTATION_DAYS = 90
    
    # CSRF
    CSRF_COOKIE_AGE = 3600  # 1 hour
    CSRF_TOKEN_LENGTH = 32


class IPSecurityManager:
    """Manages IP-based security including whitelist/blacklist and rate limiting"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def is_ip_allowed(self, ip_address: str) -> bool:
        """
        Check if IP address is allowed based on whitelist/blacklist
        
        Args:
            ip_address: IP address to check
            
        Returns:
            True if IP is allowed, False otherwise
        """
        try:
            ip = ipaddress.ip_address(ip_address)
            
            # Check cache first
            cache_key = f'ip_allowed_{ip_address}'
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Check blacklist first (takes precedence)
            if self._is_ip_blacklisted(ip):
                cache.set(cache_key, False, self.cache_timeout)
                return False
            
            # Check whitelist (if configured)
            whitelist = self._get_ip_whitelist()
            if whitelist:
                allowed = self._is_ip_in_ranges(ip, whitelist)
                cache.set(cache_key, allowed, self.cache_timeout)
                return allowed
            
            # If no whitelist configured, allow by default (unless blacklisted)
            cache.set(cache_key, True, self.cache_timeout)
            return True
            
        except (ipaddress.AddressValueError, ValueError):
            # Invalid IP format, deny access
            return False
    
    def add_to_blacklist(self, ip_address: str, reason: str = '', admin_user: AdminUser = None):
        """
        Add IP address to blacklist
        
        Args:
            ip_address: IP address to blacklist
            reason: Reason for blacklisting
            admin_user: Admin user performing the action
        """
        try:
            ip = ipaddress.ip_address(ip_address)
            
            blacklist = self._get_ip_blacklist()
            if ip_address not in blacklist:
                blacklist.append({
                    'ip': ip_address,
                    'reason': reason,
                    'added_by': admin_user.username if admin_user else 'system',
                    'added_at': timezone.now().isoformat(),
                })
                
                self._save_ip_blacklist(blacklist)
                self._clear_ip_cache(ip_address)
                
                # Log the action
                if admin_user:
                    AdminAction.objects.create(
                        admin=admin_user,
                        action_type='ip_blacklisted',
                        severity='warning',
                        title='IP Address Blacklisted',
                        description=f'IP {ip_address} added to blacklist: {reason}',
                        metadata={
                            'ip_address': ip_address,
                            'reason': reason
                        }
                    )
                    
        except (ipaddress.AddressValueError, ValueError):
            raise ValidationError('Invalid IP address format')
    
    def remove_from_blacklist(self, ip_address: str, admin_user: AdminUser = None):
        """
        Remove IP address from blacklist
        
        Args:
            ip_address: IP address to remove
            admin_user: Admin user performing the action
        """
        blacklist = self._get_ip_blacklist()
        blacklist = [entry for entry in blacklist if entry.get('ip') != ip_address]
        
        self._save_ip_blacklist(blacklist)
        self._clear_ip_cache(ip_address)
        
        # Log the action
        if admin_user:
            AdminAction.objects.create(
                admin=admin_user,
                action_type='ip_blacklist_removed',
                severity='info',
                title='IP Address Removed from Blacklist',
                description=f'IP {ip_address} removed from blacklist',
                metadata={'ip_address': ip_address}
            )
    
    def add_to_whitelist(self, ip_range: str, description: str = '', admin_user: AdminUser = None):
        """
        Add IP range to whitelist
        
        Args:
            ip_range: IP address or CIDR range
            description: Description of the range
            admin_user: Admin user performing the action
        """
        try:
            # Validate IP range
            ipaddress.ip_network(ip_range, strict=False)
            
            whitelist = self._get_ip_whitelist()
            if not any(entry.get('range') == ip_range for entry in whitelist):
                whitelist.append({
                    'range': ip_range,
                    'description': description,
                    'added_by': admin_user.username if admin_user else 'system',
                    'added_at': timezone.now().isoformat(),
                })
                
                self._save_ip_whitelist(whitelist)
                self._clear_all_ip_cache()
                
                # Log the action
                if admin_user:
                    AdminAction.objects.create(
                        admin=admin_user,
                        action_type='ip_whitelisted',
                        severity='info',
                        title='IP Range Whitelisted',
                        description=f'IP range {ip_range} added to whitelist: {description}',
                        metadata={
                            'ip_range': ip_range,
                            'description': description
                        }
                    )
                    
        except (ipaddress.AddressValueError, ValueError):
            raise ValidationError('Invalid IP address or CIDR range format')
    
    def get_failed_attempts(self, ip_address: str) -> int:
        """Get number of failed login attempts for IP"""
        cache_key = f'failed_attempts_{ip_address}'
        return cache.get(cache_key, 0)
    
    def record_failed_attempt(self, ip_address: str, username: str = ''):
        """Record a failed login attempt"""
        cache_key = f'failed_attempts_{ip_address}'
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, SecurityConfig.IP_LOCKOUT_DURATION)
        
        # Automatically blacklist IP after maximum failed attempts
        if attempts >= SecurityConfig.MAX_FAILED_ATTEMPTS:
            self.add_to_blacklist(
                ip_address, 
                f'Auto-blacklisted after {attempts} failed login attempts',
                None
            )
            
            # Log security event
            AdminAction.objects.create(
                admin=None,
                action_type='ip_auto_blacklisted',
                severity='critical',
                title='IP Auto-Blacklisted',
                description=f'IP {ip_address} auto-blacklisted after {attempts} failed attempts',
                metadata={
                    'ip_address': ip_address,
                    'failed_attempts': attempts,
                    'username_attempted': username
                }
            )
    
    def clear_failed_attempts(self, ip_address: str):
        """Clear failed login attempts for IP"""
        cache_key = f'failed_attempts_{ip_address}'
        cache.delete(cache_key)
    
    def is_rate_limited(self, ip_address: str, action: str = 'general') -> bool:
        """
        Check if IP is rate limited for specific action
        
        Args:
            ip_address: IP address to check
            action: Action type (general, login, api, etc.)
            
        Returns:
            True if rate limited, False otherwise
        """
        limits = {
            'general': SecurityConfig.DEFAULT_RATE_LIMIT,
            'login': SecurityConfig.LOGIN_RATE_LIMIT,
            'sensitive': SecurityConfig.STRICT_RATE_LIMIT,
            'api': SecurityConfig.DEFAULT_RATE_LIMIT,
        }
        
        limit = limits.get(action, SecurityConfig.DEFAULT_RATE_LIMIT)
        window = 900 if action == 'login' else 60  # 15 minutes for login, 1 minute for others
        
        cache_key = f'rate_limit_{action}_{ip_address}'
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return True
        
        # Increment counter
        cache.set(cache_key, current_count + 1, window)
        return False
    
    # Private methods
    
    def _is_ip_blacklisted(self, ip: ipaddress.IPv4Address) -> bool:
        """Check if IP is in blacklist"""
        blacklist = self._get_ip_blacklist()
        for entry in blacklist:
            try:
                if ip == ipaddress.ip_address(entry.get('ip', '')):
                    return True
            except (ipaddress.AddressValueError, ValueError):
                continue
        return False
    
    def _is_ip_in_ranges(self, ip: ipaddress.IPv4Address, ranges: List[Dict]) -> bool:
        """Check if IP is in any of the specified ranges"""
        for entry in ranges:
            try:
                network = ipaddress.ip_network(entry.get('range', ''), strict=False)
                if ip in network:
                    return True
            except (ipaddress.AddressValueError, ValueError):
                continue
        return False
    
    def _get_ip_blacklist(self) -> List[Dict]:
        """Get IP blacklist from cache/storage"""
        cache_key = 'admin_ip_blacklist'
        blacklist = cache.get(cache_key)
        
        if blacklist is None:
            # Load from settings or database
            blacklist = getattr(settings, 'ADMIN_IP_BLACKLIST', [])
            cache.set(cache_key, blacklist, 3600)  # Cache for 1 hour
        
        return blacklist
    
    def _save_ip_blacklist(self, blacklist: List[Dict]):
        """Save IP blacklist to cache/storage"""
        cache_key = 'admin_ip_blacklist'
        cache.set(cache_key, blacklist, 3600)
        
        # Also save to database for persistence
        self._persist_security_setting('ip_blacklist', blacklist)
    
    def _get_ip_whitelist(self) -> List[Dict]:
        """Get IP whitelist from cache/storage"""
        cache_key = 'admin_ip_whitelist'
        whitelist = cache.get(cache_key)
        
        if whitelist is None:
            whitelist = getattr(settings, 'ADMIN_IP_WHITELIST', [])
            cache.set(cache_key, whitelist, 3600)
        
        return whitelist
    
    def _save_ip_whitelist(self, whitelist: List[Dict]):
        """Save IP whitelist to cache/storage"""
        cache_key = 'admin_ip_whitelist'
        cache.set(cache_key, whitelist, 3600)
        
        # Also save to database for persistence
        self._persist_security_setting('ip_whitelist', whitelist)
    
    def _clear_ip_cache(self, ip_address: str):
        """Clear cache for specific IP"""
        cache_keys = [
            f'ip_allowed_{ip_address}',
            f'failed_attempts_{ip_address}',
        ]
        cache.delete_many(cache_keys)
    
    def _clear_all_ip_cache(self):
        """Clear all IP-related cache"""
        # Clear IP-related cache entries
        cache.delete_many(['admin_ip_blacklist', 'admin_ip_whitelist'])
    
    def _persist_security_setting(self, key: str, value: Any):
        """Persist security setting to database"""
        # Store security setting with extended cache duration for persistence
        cache.set(f'security_setting_{key}', value, 86400)  # 24 hours


class EncryptionManager:
    """Manages encryption for sensitive admin data"""
    
    def __init__(self):
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def encrypt_data(self, data: str) -> str:
        """
        Encrypt sensitive data
        
        Args:
            data: Plain text data to encrypt
            
        Returns:
            Encrypted data as base64 string
        """
        if not isinstance(data, str):
            data = str(data)
        
        encrypted = self.cipher.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted data
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted plain text data
        """
        try:
            encrypted = base64.b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception:
            raise ValueError('Failed to decrypt data')
    
    def hash_sensitive_data(self, data: str, salt: Optional[str] = None) -> Dict[str, str]:
        """
        Create a secure hash of sensitive data
        
        Args:
            data: Data to hash
            salt: Optional salt (generated if not provided)
            
        Returns:
            Dictionary with hash and salt
        """
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Use PBKDF2 for secure hashing
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,
        )
        
        key = base64.b64encode(kdf.derive(data.encode())).decode()
        
        return {
            'hash': key,
            'salt': salt
        }
    
    def verify_hash(self, data: str, hash_data: Dict[str, str]) -> bool:
        """
        Verify data against stored hash
        
        Args:
            data: Data to verify
            hash_data: Dictionary containing hash and salt
            
        Returns:
            True if data matches hash
        """
        try:
            verification = self.hash_sensitive_data(data, hash_data['salt'])
            return hmac.compare_digest(verification['hash'], hash_data['hash'])
        except Exception:
            return False
    
    def rotate_key(self) -> str:
        """
        Rotate encryption key and return new key
        
        Returns:
            New encryption key
        """
        new_key = Fernet.generate_key()
        
        # Store new key securely
        self._store_key(new_key)
        
        # Update instance
        self.key = new_key
        self.cipher = Fernet(new_key)
        
        # Log key rotation
        AdminAction.objects.create(
            admin=None,
            action_type='encryption_key_rotated',
            severity='info',
            title='Encryption Key Rotated',
            description='System encryption key has been rotated',
            metadata={
                'rotated_at': timezone.now().isoformat(),
                'key_id': hashlib.sha256(new_key).hexdigest()[:16]
            }
        )
        
        return new_key.decode()
    
    def _get_or_create_key(self) -> bytes:
        """Get existing key or create new one"""
        # Try to get from environment first
        key_env = os.getenv('ADMIN_ENCRYPTION_KEY')
        if key_env:
            try:
                return base64.b64decode(key_env.encode())
            except Exception:
                pass
        
        # Try to get from file
        key_file = getattr(settings, 'ADMIN_ENCRYPTION_KEY_FILE', None)
        if key_file and os.path.exists(key_file):
            try:
                with open(key_file, 'rb') as f:
                    return f.read()
            except Exception:
                pass
        
        # Generate new key
        new_key = Fernet.generate_key()
        self._store_key(new_key)
        return new_key
    
    def _store_key(self, key: bytes):
        """Store encryption key securely"""
        key_file = getattr(settings, 'ADMIN_ENCRYPTION_KEY_FILE', 'admin_encryption.key')
        
        try:
            with open(key_file, 'wb') as f:
                f.write(key)
            
            # Set secure file permissions
            os.chmod(key_file, 0o600)
            
        except Exception as e:
            # Log error but don't fail completely
            AdminAction.objects.create(
                admin=None,
                action_type='encryption_key_storage_error',
                severity='error',
                title='Encryption Key Storage Error',
                description=f'Failed to store encryption key: {str(e)}',
                metadata={'error': str(e)}
            )


class SessionSecurityManager:
    """Manages session security features"""
    
    def __init__(self):
        self.ip_manager = IPSecurityManager()
    
    def validate_session_security(self, request: HttpRequest, admin_session: 'AdminSession') -> Dict[str, Any]:
        """
        Comprehensive session security validation
        
        Args:
            request: HTTP request object
            admin_session: AdminSession to validate
            
        Returns:
            Validation results
        """
        result = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'should_terminate': False
        }
        
        # Check session expiry
        if admin_session.expires_at <= timezone.now():
            result['valid'] = False
            result['errors'].append('Session expired')
            result['should_terminate'] = True
            return result
        
        # Check IP consistency
        current_ip = self._get_client_ip(request)
        if SecurityConfig.SESSION_IP_CHECK and admin_session.ip_address != current_ip:
            result['valid'] = False
            result['errors'].append(f'IP address changed from {admin_session.ip_address} to {current_ip}')
            result['should_terminate'] = True
            
            # Log security violation
            AdminAction.objects.create(
                admin=admin_session.admin,
                action_type='session_ip_violation',
                severity='critical',
                title='Session IP Violation',
                description=f'Session IP changed from {admin_session.ip_address} to {current_ip}',
                metadata={
                    'original_ip': admin_session.ip_address,
                    'current_ip': current_ip,
                    'session_id': str(admin_session.id)
                }
            )
        
        # Check User-Agent consistency (warning only)
        current_user_agent = request.META.get('HTTP_USER_AGENT', '')
        if SecurityConfig.SESSION_USER_AGENT_CHECK and admin_session.user_agent != current_user_agent:
            result['warnings'].append('User agent changed')
            
            # Log warning
            AdminAction.objects.create(
                admin=admin_session.admin,
                action_type='session_ua_change',
                severity='warning',
                title='User Agent Changed',
                description='Session user agent changed',
                metadata={
                    'original_ua': admin_session.user_agent[:200],
                    'current_ua': current_user_agent[:200],
                    'session_id': str(admin_session.id)
                }
            )
        
        # Check for session hijacking patterns
        if self._detect_session_anomalies(request, admin_session):
            result['warnings'].append('Potential session anomalies detected')
        
        # Check concurrent sessions
        active_sessions = AdminSession.objects.filter(
            admin=admin_session.admin,
            is_active=True,
            expires_at__gt=timezone.now()
        ).count()
        
        if active_sessions > SecurityConfig.MAX_CONCURRENT_SESSIONS:
            result['warnings'].append(f'Excessive concurrent sessions: {active_sessions}')
        
        return result
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count"""
        expired_sessions = AdminSession.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )
        
        count = expired_sessions.count()
        
        if count > 0:
            expired_sessions.update(
                is_active=False,
                ended_at=timezone.now()
            )
            
            # Log cleanup
            AdminAction.objects.create(
                admin=None,
                action_type='session_cleanup',
                severity='info',
                title='Expired Sessions Cleaned',
                description=f'Cleaned up {count} expired sessions',
                metadata={'cleaned_count': count}
            )
        
        return count
    
    def terminate_suspicious_sessions(self) -> int:
        """Terminate sessions that appear suspicious"""
        # This would implement more sophisticated detection logic
        # For now, we'll terminate very old sessions
        old_threshold = timezone.now() - timedelta(days=7)
        
        old_sessions = AdminSession.objects.filter(
            created_at__lt=old_threshold,
            is_active=True
        )
        
        count = old_sessions.count()
        
        if count > 0:
            old_sessions.update(
                is_active=False,
                ended_at=timezone.now()
            )
            
            # Log termination
            AdminAction.objects.create(
                admin=None,
                action_type='suspicious_sessions_terminated',
                severity='warning',
                title='Suspicious Sessions Terminated',
                description=f'Terminated {count} potentially suspicious sessions',
                metadata={'terminated_count': count}
            )
        
        return count
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
    
    def _detect_session_anomalies(self, request: HttpRequest, admin_session: 'AdminSession') -> bool:
        """Detect potential session anomalies"""
        # Implement anomaly detection logic
        # For example: rapid location changes, unusual access patterns, etc.
        
        # Check for rapid requests (potential automation)
        cache_key = f'request_frequency_{admin_session.id}'
        recent_requests = cache.get(cache_key, 0)
        
        if recent_requests > 100:  # More than 100 requests in last minute
            return True
        
        cache.set(cache_key, recent_requests + 1, 60)
        return False


class CSRFEnhancement:
    """Enhanced CSRF protection for admin panel"""
    
    @staticmethod
    def generate_enhanced_token(request: HttpRequest) -> str:
        """Generate enhanced CSRF token with additional entropy"""
        base_token = get_token(request)
        
        # Add additional entropy
        timestamp = str(int(timezone.now().timestamp()))
        session_id = request.session.session_key or 'no-session'
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create composite token
        composite_data = f"{base_token}:{timestamp}:{session_id}:{hashlib.sha256(user_agent.encode()).hexdigest()[:16]}"
        
        # Hash the composite data
        enhanced_token = hashlib.sha256(composite_data.encode()).hexdigest()
        
        # Store in session for validation
        request.session['enhanced_csrf_token'] = enhanced_token
        request.session['enhanced_csrf_timestamp'] = timestamp
        
        return enhanced_token
    
    @staticmethod
    def validate_enhanced_token(request: HttpRequest, token: str) -> bool:
        """Validate enhanced CSRF token"""
        stored_token = request.session.get('enhanced_csrf_token')
        stored_timestamp = request.session.get('enhanced_csrf_timestamp')
        
        if not stored_token or not stored_timestamp:
            return False
        
        # Check token match
        if not hmac.compare_digest(stored_token, token):
            return False
        
        # Check token age
        token_age = timezone.now().timestamp() - float(stored_timestamp)
        if token_age > SecurityConfig.CSRF_COOKIE_AGE:
            return False
        
        return True


# Security decorators

def ip_whitelist_required(view_func):
    """Decorator to require IP whitelist access"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        ip_manager = IPSecurityManager()
        client_ip = ip_manager._get_client_ip(request)
        
        if not ip_manager.is_ip_allowed(client_ip):
            # Log unauthorized access
            AdminAction.objects.create(
                admin=None,
                action_type='ip_access_denied',
                severity='warning',
                title='IP Access Denied',
                description=f'Access denied for IP {client_ip}',
                metadata={'ip_address': client_ip, 'path': request.path}
            )
            
            return JsonResponse({
                'error': 'Access denied from this IP address'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def rate_limit_required(action: str = 'general'):
    """Decorator for rate limiting"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip_manager = IPSecurityManager()
            client_ip = ip_manager._get_client_ip(request)
            
            if ip_manager.is_rate_limited(client_ip, action):
                return JsonResponse({
                    'error': 'Rate limit exceeded. Please try again later.'
                }, status=429)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def enhanced_csrf_protect(view_func):
    """Enhanced CSRF protection decorator"""
    @wraps(view_func)
    @csrf_protect
    def wrapper(request, *args, **kwargs):
        if request.method == 'POST':
            enhanced_token = request.POST.get('enhanced_csrf_token') or request.META.get('HTTP_X_ENHANCED_CSRF_TOKEN')
            
            if not enhanced_token or not CSRFEnhancement.validate_enhanced_token(request, enhanced_token):
                return JsonResponse({
                    'error': 'Enhanced CSRF validation failed'
                }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# Initialize security managers
ip_security = IPSecurityManager()
encryption_manager = EncryptionManager()
session_security = SessionSecurityManager()


def get_security_status() -> Dict[str, Any]:
    """Get overall security status for dashboard"""
    return {
        'ip_blacklist_count': len(ip_security._get_ip_blacklist()),
        'ip_whitelist_count': len(ip_security._get_ip_whitelist()),
        'active_sessions': AdminSession.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).count(),
        'security_events_24h': AdminAction.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24),
            severity__in=['warning', 'error', 'critical']
        ).count(),
        'last_key_rotation': timezone.now() - timedelta(days=30),  # Placeholder
    }