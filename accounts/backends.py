"""
Custom authentication backends for GupShup
Supports login with email or Indian phone number (+91)
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
import re

User = get_user_model()


class EmailOrPhoneBackend(ModelBackend):
    """
    Custom authentication backend that allows users to login with either:
    1. Email address
    2. Indian phone number (+91XXXXXXXXXX)
    3. Username (default Django behavior)
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        if username is None or password is None:
            return None
        
        # Clean and validate the input
        username = str(username).strip()
        
        # Try to find user by multiple methods
        user = None
        
        # Method 1: Direct username match
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            pass
        
        # Method 2: Email match
        if not user and '@' in username:
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                pass
        
        # Method 3: Phone number match (Indian +91)
        if not user and self._is_indian_phone(username):
            # Normalize phone number format
            phone_normalized = self._normalize_indian_phone(username)
            try:
                user = User.objects.get(phone_number=phone_normalized)
            except User.DoesNotExist:
                pass
        
        # Method 4: If still not found, try combined search
        if not user:
            try:
                phone_normalized = self._normalize_indian_phone(username) if self._is_indian_phone(username) else None
                
                query = Q(username=username) | Q(email=username)
                if phone_normalized:
                    query |= Q(phone_number=phone_normalized)
                
                user = User.objects.get(query)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass
        
        # Verify password and return user if valid
        if user and self._check_password(user, password):
            return user
        
        return None
    
    def _is_indian_phone(self, phone_str):
        """Check if string looks like an Indian phone number"""
        # Remove all non-digits
        digits_only = re.sub(r'\D', '', phone_str)
        
        # Indian phone patterns:
        # +91XXXXXXXXXX (10 digits after +91)
        # 91XXXXXXXXXX (10 digits after 91)
        # XXXXXXXXXX (10 digits, assuming Indian)
        
        if len(digits_only) == 10:  # 10 digits - assume Indian
            return True
        elif len(digits_only) == 12 and digits_only.startswith('91'):  # 91XXXXXXXXXX
            return True
        elif len(digits_only) == 13 and digits_only.startswith('91'):  # +91 but parsed as digits
            return True
        
        return False
    
    def _normalize_indian_phone(self, phone_str):
        """Normalize phone number to Django PhoneNumber format"""
        if not phone_str:
            return None
        
        # Remove all non-digits
        digits_only = re.sub(r'\D', '', phone_str)
        
        # Convert to +91XXXXXXXXXX format
        if len(digits_only) == 10:
            # Assume Indian number
            return f"+91{digits_only}"
        elif len(digits_only) == 12 and digits_only.startswith('91'):
            # 91XXXXXXXXXX -> +91XXXXXXXXXX
            return f"+{digits_only}"
        elif len(digits_only) >= 12 and '91' in digits_only[:3]:
            # Handle various formats
            if digits_only.startswith('91'):
                return f"+{digits_only[:12]}"
        
        # If already in +91 format or other, return as-is after basic cleanup
        if phone_str.startswith('+91') and len(phone_str) == 13:
            return phone_str
        
        return None
    
    def _check_password(self, user, password):
        """Check if password is correct and user is active"""
        return user.check_password(password) and self.user_can_authenticate(user)
    
    def get_user(self, user_id):
        """Retrieve user by primary key"""
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        
        return user if self.user_can_authenticate(user) else None


class PhoneNumberBackend(ModelBackend):
    """
    Simplified phone number only backend
    """
    
    def authenticate(self, request, phone_number=None, password=None, **kwargs):
        if not phone_number or not password:
            return None
        
        try:
            # Try to find user by phone number
            user = User.objects.get(phone_number=phone_number)
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except User.DoesNotExist:
            pass
        
        return None