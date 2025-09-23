"""
Admin Panel Forms with Enhanced Validation

This module contains all forms used in the admin panel with proper validation,
security features, and Indian context support.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField
from datetime import datetime, timedelta
import re

from .models import (
    AdminUser, UserWarning, BannedUser, ModeratedContent, 
    PlatformAnnouncement, AdminAction
)
from posts.models import Post

User = get_user_model()

class AdminLoginForm(forms.Form):
    """
    Enhanced admin login form with security features
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your admin username',
            'autofocus': True,
            'autocomplete': 'username'
        }),
        label=_('Username'),
        help_text=_('Enter your admin username')
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password'
        }),
        label=_('Password'),
        help_text=_('Enter your admin password')
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Keep me signed in'),
        help_text=_('Stay logged in for longer (not recommended on shared computers)')
    )
    
    # CAPTCHA field (can be integrated with django-recaptcha)
    captcha_response = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label=_('Captcha Response')
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.require_captcha = kwargs.pop('require_captcha', False)
        super().__init__(*args, **kwargs)
        
        if self.require_captcha:
            self.fields['captcha_response'].required = True
            self.fields['captcha_response'].widget = forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter the characters you see'
            })
    
    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError(_('Username is required'))
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if username and password:
            from .auth import AdminAuthenticationBackend
            auth_backend = AdminAuthenticationBackend()
            
            admin_user = auth_backend.authenticate(
                self.request, username=username, password=password
            )
            
            if not admin_user:
                raise ValidationError(
                    _('Invalid username or password. Please try again.')
                )
            
            # Store authenticated admin for the view to use
            self._admin_user = admin_user
        
        return cleaned_data
    
    def get_admin_user(self):
        return getattr(self, '_admin_user', None)


class UserSearchForm(forms.Form):
    """
    Advanced user search form with multiple filters
    """
    SORT_CHOICES = [
        ('-date_joined', _('Newest First')),
        ('date_joined', _('Oldest First')),
        ('username', _('Username A-Z')),
        ('-username', _('Username Z-A')),
        ('-posts_count', _('Most Posts')),
        ('-followers_count', _('Most Followers')),
        ('-last_seen', _('Recently Active')),
    ]
    
    STATUS_CHOICES = [
        ('', _('All Users')),
        ('active', _('Active Users')),
        ('inactive', _('Inactive Users')),
        ('banned', _('Banned Users')),
        ('verified', _('Verified Users')),
    ]
    
    query = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by username, email, name, or phone',
            'data-toggle': 'tooltip',
            'title': 'Search users by username, email, name, or phone number'
        }),
        label=_('Search')
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Status Filter')
    )
    
    state = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('State Filter')
    )
    
    verified_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Verified users only')
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('Joined From')
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('Joined To')
    )
    
    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='-date_joined',
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Sort By')
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate state choices dynamically from User model
        from accounts.models import GupShupUser
        state_choices = [('', _('All States'))]
        state_choices.extend(GupShupUser._meta.get_field('state').choices)
        self.fields['state'].choices = state_choices
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError(_('Start date cannot be after end date'))
        
        return cleaned_data


class UserBanForm(forms.Form):
    """
    Form for banning users with comprehensive options
    """
    BAN_DURATION_CHOICES = [
        ('1', _('1 Day')),
        ('3', _('3 Days')),
        ('7', _('1 Week')),
        ('14', _('2 Weeks')),
        ('30', _('1 Month')),
        ('90', _('3 Months')),
        ('365', _('1 Year')),
        ('permanent', _('Permanent')),
        ('custom', _('Custom Duration')),
    ]
    
    user_id = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    ban_type = forms.ChoiceField(
        choices=BannedUser.BAN_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Ban Type'),
        help_text=_('Type of ban to apply')
    )
    
    duration = forms.ChoiceField(
        choices=BAN_DURATION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'toggleCustomDuration(this.value)'
        }),
        label=_('Duration'),
        help_text=_('How long should this ban last?')
    )
    
    custom_duration = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=3650,  # 10 years max
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'style': 'display: none;',
            'placeholder': 'Enter days'
        }),
        label=_('Custom Duration (Days)'),
        help_text=_('Number of days for custom duration')
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter the reason for banning this user...',
            'required': True
        }),
        label=_('Internal Reason'),
        help_text=_('Detailed reason for admin records')
    )
    
    public_reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reason shown to the user (optional)',
            'maxlength': 200
        }),
        required=False,
        label=_('Public Reason'),
        help_text=_('Brief reason shown to the user (leave empty for generic message)')
    )
    
    notify_user = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Notify user via email'),
        help_text=_('Send an email notification to the user')
    )
    
    related_post = forms.ModelChoiceField(
        queryset=Post.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Related Post'),
        help_text=_('Post that triggered this ban (if applicable)')
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Get recent posts by this user
            recent_posts = Post.objects.filter(
                author=user
            ).order_by('-created_at')[:20]
            
            self.fields['related_post'].queryset = recent_posts
            self.fields['related_post'].empty_label = _('Not related to a specific post')
    
    def clean(self):
        cleaned_data = super().clean()
        duration = cleaned_data.get('duration')
        custom_duration = cleaned_data.get('custom_duration')
        
        if duration == 'custom' and not custom_duration:
            raise ValidationError({
                'custom_duration': _('Custom duration is required when "Custom Duration" is selected')
            })
        
        if duration != 'custom':
            cleaned_data['custom_duration'] = None
        
        return cleaned_data
    
    def get_ban_expires_at(self):
        """Calculate ban expiration datetime"""
        duration = self.cleaned_data['duration']
        
        if duration == 'permanent':
            return None
        
        if duration == 'custom':
            days = self.cleaned_data['custom_duration']
        else:
            days = int(duration)
        
        return timezone.now() + timedelta(days=days)


class UserWarningForm(forms.Form):
    """
    Form for issuing warnings to users
    """
    user_id = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    warning_type = forms.ChoiceField(
        choices=UserWarning.WARNING_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Warning Type'),
        help_text=_('Category of the warning')
    )
    
    severity = forms.ChoiceField(
        choices=UserWarning.SEVERITY_LEVELS,
        initial='medium',
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Severity Level'),
        help_text=_('How serious is this warning?')
    )
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a clear title for this warning'
        }),
        label=_('Warning Title'),
        help_text=_('Brief title that summarizes the warning')
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter detailed message explaining the warning...'
        }),
        label=_('Warning Message'),
        help_text=_('Detailed explanation of the warning and what the user should do')
    )
    
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        label=_('Expiry Date (Optional)'),
        help_text=_('When should this warning expire? Leave empty for permanent warning')
    )
    
    auto_action = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., "Account restricted", "Posts hidden"'
        }),
        label=_('Automatic Action Taken'),
        help_text=_('Any automatic action taken along with this warning')
    )
    
    related_post = forms.ModelChoiceField(
        queryset=Post.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Related Post'),
        help_text=_('Post that triggered this warning (if applicable)')
    )
    
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Send email notification'),
        help_text=_('Email the warning to the user')
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Get recent posts by this user
            recent_posts = Post.objects.filter(
                author=user
            ).order_by('-created_at')[:20]
            
            self.fields['related_post'].queryset = recent_posts
            self.fields['related_post'].empty_label = _('Not related to a specific post')
    
    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError(_('Expiry date must be in the future'))
        return expires_at


class PostModerationForm(forms.Form):
    """
    Form for moderating posts with various actions
    """
    ACTION_CHOICES = [
        ('approve', _('Approve Post')),
        ('hide', _('Hide Post')),
        ('delete', _('Delete Post')),
        ('flag', _('Flag for Review')),
        ('warn_user', _('Warn User')),
        ('ban_user', _('Ban User')),
    ]
    
    post_id = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'updateModerationOptions(this.value)'
        }),
        label=_('Action to Take'),
        help_text=_('What action should be taken on this post?')
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter the reason for this action...'
        }),
        label=_('Reason'),
        help_text=_('Explain why you are taking this action')
    )
    
    notify_user = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Notify user'),
        help_text=_('Send notification to the post author')
    )
    
    public_reason = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reason shown to user (optional)'
        }),
        label=_('Public Reason'),
        help_text=_('Brief reason shown to the user (leave empty for generic message)')
    )
    
    # Additional fields for warnings/bans
    warning_severity = forms.ChoiceField(
        choices=UserWarning.SEVERITY_LEVELS,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'style': 'display: none;'
        }),
        label=_('Warning Severity')
    )
    
    ban_duration = forms.ChoiceField(
        choices=UserBanForm.BAN_DURATION_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'style': 'display: none;'
        }),
        label=_('Ban Duration')
    )


class BulkActionForm(forms.Form):
    """
    Form for performing bulk actions on multiple items
    """
    ACTION_CHOICES = [
        ('', _('Select Action')),
        ('delete_users', _('Delete Selected Users')),
        ('ban_users', _('Ban Selected Users')),
        ('unban_users', _('Unban Selected Users')),
        ('verify_users', _('Verify Selected Users')),
        ('unverify_users', _('Remove Verification')),
        ('delete_posts', _('Delete Selected Posts')),
        ('hide_posts', _('Hide Selected Posts')),
        ('approve_posts', _('Approve Selected Posts')),
        ('export_users', _('Export User Data')),
        ('export_posts', _('Export Post Data')),
    ]
    
    selected_items = forms.CharField(
        widget=forms.HiddenInput(),
        help_text=_('Comma-separated list of item IDs')
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'updateBulkOptions(this.value)'
        }),
        label=_('Bulk Action'),
        help_text=_('Choose action to perform on selected items')
    )
    
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter reason for this bulk action...'
        }),
        label=_('Reason'),
        help_text=_('Reason for performing this bulk action')
    )
    
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('I understand this action cannot be undone'),
        help_text=_('Confirm that you want to perform this bulk action')
    )
    
    def clean_selected_items(self):
        selected_items = self.cleaned_data.get('selected_items', '')
        if not selected_items:
            raise ValidationError(_('No items selected'))
        
        try:
            item_ids = [item.strip() for item in selected_items.split(',') if item.strip()]
            if not item_ids:
                raise ValidationError(_('No valid items selected'))
            return item_ids
        except Exception:
            raise ValidationError(_('Invalid item selection format'))


class PlatformAnnouncementForm(forms.ModelForm):
    """
    Form for creating platform-wide announcements
    """
    class Meta:
        model = PlatformAnnouncement
        fields = [
            'title', 'message', 'announcement_type', 'target_audience',
            'target_regions', 'is_urgent', 'show_on_login', 'show_on_homepage',
            'starts_at', 'ends_at', 'action_text', 'action_url'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter announcement title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Enter announcement message...'
            }),
            'announcement_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'target_audience': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'toggleRegionField(this.value)'
            }),
            'target_regions': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Maharashtra, Delhi, Karnataka'
            }),
            'starts_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'ends_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'action_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., "Learn More", "Update Now"'
            }),
            'action_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make starts_at default to current time
        if not self.instance.pk:
            self.fields['starts_at'].initial = timezone.now()
    
    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get('starts_at')
        ends_at = cleaned_data.get('ends_at')
        target_audience = cleaned_data.get('target_audience')
        target_regions = cleaned_data.get('target_regions')
        
        if starts_at and ends_at and starts_at >= ends_at:
            raise ValidationError(_('End date must be after start date'))
        
        if target_audience == 'specific_regions' and not target_regions:
            raise ValidationError({
                'target_regions': _('Target regions are required when audience is "Specific Regions"')
            })
        
        return cleaned_data


class AdminUserForm(forms.ModelForm):
    """
    Form for creating/editing admin users
    """
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave empty to keep current password'
        }),
        label=_('Password'),
        help_text=_('Leave empty when editing to keep current password')
    )
    
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        label=_('Confirm Password')
    )
    
    class Meta:
        model = AdminUser
        fields = [
            'username', 'email', 'first_name', 'last_name', 'phone_number',
            'role', 'status', 'can_manage_users', 'can_manage_posts',
            'can_view_analytics', 'can_send_warnings', 'can_ban_users',
            'can_delete_posts', 'can_manage_system', 'can_access_reports',
            'can_manage_admins', 'can_export_data', 'can_moderate_content',
            'session_timeout_minutes', 'allowed_ip_addresses'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'session_timeout_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'allowed_ip_addresses': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '192.168.1.1, 10.0.0.1'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance.pk:
            self.fields['password'].help_text = _('Leave empty to keep current password')
            self.fields['password'].required = False
        else:
            self.fields['password'].required = True
            self.fields['password'].help_text = _('Enter a strong password for this admin')
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and password != confirm_password:
            raise ValidationError(_('Passwords do not match'))
        
        return cleaned_data
    
    def save(self, commit=True):
        admin_user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        
        if password:
            admin_user.set_password(password)
        
        if commit:
            admin_user.save()
        
        return admin_user


# Indian Context Validators

def validate_indian_phone(value):
    """Validate Indian phone number format"""
    if not value.startswith('+91'):
        raise ValidationError(_('Phone number must start with +91'))
    
    # Remove +91 and check if remaining digits are valid
    digits = value[3:]
    if not digits.isdigit() or len(digits) != 10:
        raise ValidationError(_('Invalid Indian phone number format'))

def validate_indian_state(value):
    """Validate Indian state code"""
    from accounts.models import GupShupUser
    valid_states = [choice[0] for choice in GupShupUser._meta.get_field('state').choices]
    if value not in valid_states:
        raise ValidationError(_('Invalid Indian state code'))