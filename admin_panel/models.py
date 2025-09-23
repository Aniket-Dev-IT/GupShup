from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import validate_email
from phonenumber_field.modelfields import PhoneNumberField
import uuid
import json
from datetime import timedelta

User = get_user_model()


class AdminUserManager(BaseUserManager):
    """
    Custom manager for AdminUser
    """
    def create_admin(self, username, email, password, **extra_fields):
        """Create and save admin user"""
        if not username:
            raise ValueError(_('Username is required'))
        if not email:
            raise ValueError(_('Email is required'))
        
        validate_email(email)
        email = self.normalize_email(email)
        
        admin = self.model(
            username=username,
            email=email,
            **extra_fields
        )
        admin.set_password(password)
        admin.save(using=self._db)
        return admin
    
    def create_superadmin(self, username, email, password, **extra_fields):
        """Create super admin with all permissions"""
        extra_fields.setdefault('role', 'super_admin')
        extra_fields.setdefault('can_manage_users', True)
        extra_fields.setdefault('can_manage_posts', True)
        extra_fields.setdefault('can_view_analytics', True)
        extra_fields.setdefault('can_send_warnings', True)
        extra_fields.setdefault('can_ban_users', True)
        extra_fields.setdefault('can_delete_posts', True)
        extra_fields.setdefault('can_manage_system', True)
        extra_fields.setdefault('can_access_reports', True)
        extra_fields.setdefault('can_manage_admins', True)
        
        return self.create_admin(username, email, password, **extra_fields)


class AdminUser(AbstractBaseUser):
    """
    Enhanced Admin User model with comprehensive permissions and security
    """
    ROLE_CHOICES = [
        ('super_admin', _('Super Administrator')),
        ('admin', _('Administrator')),
        ('moderator', _('Moderator')),
        ('analyst', _('Analytics Viewer')),
    ]
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('suspended', _('Suspended')),
        ('locked', _('Locked')),
    ]
    
    # Primary Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    
    # Role and Status
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Contact Information
    phone_number = PhoneNumberField(
        region='IN', blank=True, null=True,
        help_text=_('Admin contact number')
    )
    
    # Enhanced Permissions
    can_manage_users = models.BooleanField(default=True)
    can_manage_posts = models.BooleanField(default=True)
    can_view_analytics = models.BooleanField(default=True)
    can_send_warnings = models.BooleanField(default=True)
    can_ban_users = models.BooleanField(default=False)
    can_delete_posts = models.BooleanField(default=True)
    can_manage_system = models.BooleanField(default=False)
    can_access_reports = models.BooleanField(default=True)
    can_manage_admins = models.BooleanField(default=False)
    can_export_data = models.BooleanField(default=False)
    can_moderate_content = models.BooleanField(default=True)
    
    # Security Settings
    require_2fa = models.BooleanField(default=False)
    allowed_ip_addresses = models.TextField(
        blank=True,
        help_text=_('Comma-separated IP addresses. Leave empty for no restriction.')
    )
    session_timeout_minutes = models.PositiveIntegerField(
        default=480,  # 8 hours
        help_text=_('Session timeout in minutes')
    )
    
    # Activity Tracking
    last_login = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    
    # Account Status
    is_active = models.BooleanField(default=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_admins'
    )
    
    objects = AdminUserManager()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
    class Meta:
        db_table = 'gupshup_admin_users'
        verbose_name = _('Admin User')
        verbose_name_plural = _('Admin Users')
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['role']),
            models.Index(fields=['last_login']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        return self.first_name
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def has_permission(self, permission):
        """Check if admin has specific permission"""
        if self.is_super_admin():
            return True
        return getattr(self, f'can_{permission}', False)
    
    def check_password(self, raw_password):
        """Check password using Django's check_password"""
        return check_password(raw_password, self.password)
    
    def set_password(self, raw_password):
        """Set password using Django's make_password"""
        self.password = make_password(raw_password)
        self.password_changed_at = timezone.now()
    
    def get_session_timeout(self):
        """Get session timeout as timedelta"""
        return timedelta(minutes=self.session_timeout_minutes)
    
    def is_ip_allowed(self, ip_address):
        """Check if IP address is allowed"""
        if not self.allowed_ip_addresses:
            return True
        allowed_ips = [ip.strip() for ip in self.allowed_ip_addresses.split(',')]
        return ip_address in allowed_ips
    
    def increment_failed_login(self):
        """Increment failed login attempts"""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        self.save(update_fields=['failed_login_attempts', 'last_failed_login'])
    
    def reset_failed_login(self):
        """Reset failed login attempts"""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.save(update_fields=['failed_login_attempts', 'last_failed_login'])
    
    def is_locked(self):
        """Check if account is locked due to failed attempts"""
        if self.failed_login_attempts >= 5:
            if self.last_failed_login:
                return timezone.now() - self.last_failed_login < timedelta(minutes=30)
        return False


class AdminSession(models.Model):
    """
    Track admin sessions for security
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        AdminUser, on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Geographic data
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'gupshup_admin_sessions'
        verbose_name = _('Admin Session')
        verbose_name_plural = _('Admin Sessions')
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['admin', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.admin.username} - {self.ip_address}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at


class UserWarning(models.Model):
    """
    Enhanced warning system for users with escalation support
    """
    WARNING_TYPES = [
        ('inappropriate_content', _('Inappropriate Content')),
        ('spam', _('Spam')),
        ('harassment', _('Harassment')),
        ('fake_profile', _('Fake Profile')),
        ('copyright_violation', _('Copyright Violation')),
        ('terms_violation', _('Terms Violation')),
        ('hate_speech', _('Hate Speech')),
        ('misinformation', _('Misinformation')),
        ('adult_content', _('Adult Content')),
        ('violence', _('Violence')),
        ('other', _('Other')),
    ]
    
    SEVERITY_LEVELS = [
        ('info', _('Info')),
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('acknowledged', _('Acknowledged')),
        ('resolved', _('Resolved')),
        ('escalated', _('Escalated')),
        ('expired', _('Expired')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='warnings')
    admin = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, 
        related_name='issued_warnings'
    )
    
    warning_type = models.CharField(max_length=30, choices=WARNING_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # References
    related_post = models.ForeignKey(
        'posts.Post', on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='warnings'
    )
    parent_warning = models.ForeignKey(
        'self', on_delete=models.CASCADE, 
        null=True, blank=True, related_name='escalations'
    )
    
    # Actions
    auto_action = models.CharField(
        max_length=50, blank=True,
        help_text=_('Automatic action taken (ban, restriction, etc.)')
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text=_('Warning expiry date')
    )
    
    # User response
    user_response = models.TextField(
        blank=True,
        help_text=_('User\'s response to warning')
    )
    user_response_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Email notifications
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'gupshup_user_warnings'
        ordering = ['-created_at']
        verbose_name = _('User Warning')
        verbose_name_plural = _('User Warnings')
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['admin', 'created_at']),
        ]
    
    def __str__(self):
        return f"Warning for {self.user.username}: {self.title}"
    
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_severity_class(self):
        """Return CSS class for severity level"""
        classes = {
            'info': 'info',
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'dark'
        }
        return classes.get(self.severity, 'secondary')


class AdminAction(models.Model):
    """
    Comprehensive audit log for all admin actions
    """
    ACTION_TYPES = [
        # User Management
        ('user_created', _('User Created')),
        ('user_updated', _('User Updated')),
        ('user_deleted', _('User Deleted')),
        ('user_banned', _('User Banned')),
        ('user_unbanned', _('User Unbanned')),
        ('user_suspended', _('User Suspended')),
        ('user_activated', _('User Activated')),
        ('user_verified', _('User Verified')),
        
        # Content Management
        ('post_deleted', _('Post Deleted')),
        ('post_flagged', _('Post Flagged')),
        ('post_approved', _('Post Approved')),
        ('post_hidden', _('Post Hidden')),
        ('comment_deleted', _('Comment Deleted')),
        
        # Warning System
        ('warning_issued', _('Warning Issued')),
        ('warning_resolved', _('Warning Resolved')),
        ('warning_escalated', _('Warning Escalated')),
        
        # System Actions
        ('login', _('Admin Login')),
        ('logout', _('Admin Logout')),
        ('password_changed', _('Password Changed')),
        ('settings_changed', _('Settings Changed')),
        ('bulk_action', _('Bulk Action Performed')),
        ('data_export', _('Data Export')),
        ('announcement_sent', _('Announcement Sent')),
        
        # Admin Management
        ('admin_created', _('Admin Created')),
        ('admin_updated', _('Admin Updated')),
        ('admin_permissions_changed', _('Admin Permissions Changed')),
        
        # Security
        ('failed_login', _('Failed Login Attempt')),
        ('account_locked', _('Account Locked')),
        ('suspicious_activity', _('Suspicious Activity')),
    ]
    
    SEVERITY_LEVELS = [
        ('info', _('Info')),
        ('warning', _('Warning')),
        ('error', _('Error')),
        ('critical', _('Critical')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, 
        related_name='actions'
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    severity = models.CharField(
        max_length=10, choices=SEVERITY_LEVELS, default='info'
    )
    
    # Target information
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='admin_actions_received'
    )
    target_post = models.ForeignKey(
        'posts.Post', on_delete=models.SET_NULL, null=True, blank=True
    )
    target_admin = models.ForeignKey(
        'AdminUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='admin_actions_received'
    )
    
    # Action details
    title = models.CharField(max_length=200, default='Admin Action')
    description = models.TextField(default='Admin action performed')
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    
    # Additional data (JSON format)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Status and tracking
    status = models.CharField(
        max_length=20, 
        choices=[('success', _('Success')), ('failed', _('Failed'))],
        default='success'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'gupshup_admin_actions'
        ordering = ['-created_at']
        verbose_name = _('Admin Action')
        verbose_name_plural = _('Admin Actions')
        indexes = [
            models.Index(fields=['admin', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['target_user', 'created_at']),
        ]
    
    def __str__(self):
        admin_name = self.admin.username if self.admin else 'System'
        return f"{admin_name}: {self.get_action_type_display()}"
    
    def get_severity_class(self):
        """Return CSS class for severity"""
        classes = {
            'info': 'info',
            'warning': 'warning',
            'error': 'danger',
            'critical': 'dark'
        }
        return classes.get(self.severity, 'secondary')


class BannedUser(models.Model):
    """
    Enhanced user ban system with appeal process and detailed tracking
    """
    BAN_TYPES = [
        ('temporary', _('Temporary Ban')),
        ('permanent', _('Permanent Ban')),
        ('shadow', _('Shadow Ban')),
        ('content_only', _('Content Ban Only')),
        ('interaction_ban', _('Interaction Ban')),
    ]
    
    APPEAL_STATUS = [
        ('none', _('No Appeal')),
        ('submitted', _('Appeal Submitted')),
        ('under_review', _('Under Review')),
        ('approved', _('Appeal Approved')),
        ('rejected', _('Appeal Rejected')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='ban_record'
    )
    admin = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, 
        related_name='banned_users'
    )
    
    ban_type = models.CharField(max_length=20, choices=BAN_TYPES, default='temporary')
    reason = models.TextField()
    public_reason = models.CharField(
        max_length=200, blank=True,
        help_text=_('Reason shown to the user')
    )
    
    # Duration and status
    banned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Related content
    related_post = models.ForeignKey(
        'posts.Post', on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='bans'
    )
    related_warning = models.ForeignKey(
        UserWarning, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resulting_bans'
    )
    
    # Appeal system
    appeal_status = models.CharField(
        max_length=20, choices=APPEAL_STATUS, default='none'
    )
    appeal_message = models.TextField(blank=True)
    appeal_submitted_at = models.DateTimeField(null=True, blank=True)
    appeal_reviewed_by = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_appeals'
    )
    appeal_reviewed_at = models.DateTimeField(null=True, blank=True)
    appeal_response = models.TextField(blank=True)
    
    # Escalation
    escalated_to_admin = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='escalated_bans'
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    
    # Notifications
    user_notified = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'gupshup_banned_users'
        ordering = ['-banned_at']
        verbose_name = _('Banned User')
        verbose_name_plural = _('Banned Users')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['ban_type', 'banned_at']),
            models.Index(fields=['appeal_status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Ban: {self.user.username} ({self.get_ban_type_display()})"
    
    def is_expired(self):
        if self.ban_type == 'permanent':
            return False
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def can_appeal(self):
        """Check if user can submit an appeal"""
        return self.appeal_status in ['none', 'rejected'] and self.is_active
    
    def get_remaining_time(self):
        """Get remaining ban time as timedelta"""
        if self.ban_type == 'permanent' or not self.expires_at:
            return None
        remaining = self.expires_at - timezone.now()
        return remaining if remaining.total_seconds() > 0 else None


class ModeratedContent(models.Model):
    """
    Content moderation queue for posts requiring review
    """
    CONTENT_TYPES = [
        ('post', _('Post')),
        ('comment', _('Comment')),
        ('user_profile', _('User Profile')),
        ('image', _('Image')),
        ('video', _('Video')),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('flagged', _('Flagged for Review')),
        ('escalated', _('Escalated')),
    ]
    
    PRIORITY_LEVELS = [
        ('low', _('Low')),
        ('normal', _('Normal')),
        ('high', _('High')),
        ('urgent', _('Urgent')),
    ]
    
    FLAG_REASONS = [
        ('spam', _('Spam')),
        ('inappropriate', _('Inappropriate Content')),
        ('harassment', _('Harassment')),
        ('fake', _('Fake Content')),
        ('violence', _('Violence')),
        ('hate_speech', _('Hate Speech')),
        ('adult_content', _('Adult Content')),
        ('copyright', _('Copyright Violation')),
        ('misinformation', _('Misinformation')),
        ('other', _('Other')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Content information
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    content_id = models.CharField(max_length=100)  # ID of the content
    content_url = models.URLField(blank=True)
    content_preview = models.TextField(blank=True)
    
    # References
    post = models.ForeignKey(
        'posts.Post', on_delete=models.CASCADE, 
        null=True, blank=True, related_name='moderation_records'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, 
        related_name='moderated_content'
    )
    
    # Moderation details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    flag_reason = models.CharField(max_length=30, choices=FLAG_REASONS)
    
    # Reporter information
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reported_content'
    )
    report_reason = models.TextField(blank=True)
    auto_flagged = models.BooleanField(default=False)
    
    # Moderator actions
    reviewed_by = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_content'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderator_notes = models.TextField(blank=True)
    action_taken = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'gupshup_moderated_content'
        ordering = ['-created_at']
        verbose_name = _('Moderated Content')
        verbose_name_plural = _('Moderated Content')
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['content_type', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['reviewed_by', 'reviewed_at']),
        ]
    
    def __str__(self):
        return f"{self.get_content_type_display()} by {self.user.username} - {self.get_status_display()}"
    
    def get_priority_class(self):
        """Return CSS class for priority"""
        classes = {
            'low': 'success',
            'normal': 'info',
            'high': 'warning',
            'urgent': 'danger'
        }
        return classes.get(self.priority, 'secondary')


class PlatformAnnouncement(models.Model):
    """
    System-wide announcements from admins to users
    """
    ANNOUNCEMENT_TYPES = [
        ('info', _('Information')),
        ('warning', _('Warning')),
        ('maintenance', _('Maintenance')),
        ('feature', _('New Feature')),
        ('policy', _('Policy Update')),
        ('celebration', _('Celebration')),
    ]
    
    TARGET_AUDIENCES = [
        ('all', _('All Users')),
        ('active', _('Active Users Only')),
        ('verified', _('Verified Users')),
        ('new_users', _('New Users (< 30 days)')),
        ('power_users', _('Power Users (> 100 posts)')),
        ('specific_regions', _('Specific Regions')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPES)
    
    # Display settings
    is_active = models.BooleanField(default=True)
    is_urgent = models.BooleanField(default=False)
    show_on_login = models.BooleanField(default=False)
    show_on_homepage = models.BooleanField(default=True)
    
    # Targeting
    target_audience = models.CharField(max_length=20, choices=TARGET_AUDIENCES)
    target_regions = models.TextField(
        blank=True,
        help_text=_('Comma-separated list of states/cities for regional targeting')
    )
    
    # Scheduling
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    
    # Creator and tracking
    created_by = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True,
        related_name='announcements'
    )
    views_count = models.PositiveIntegerField(default=0)
    clicks_count = models.PositiveIntegerField(default=0)
    
    # Action button (optional)
    action_text = models.CharField(max_length=50, blank=True)
    action_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'gupshup_platform_announcements'
        ordering = ['-created_at']
        verbose_name = _('Platform Announcement')
        verbose_name_plural = _('Platform Announcements')
        indexes = [
            models.Index(fields=['is_active', 'starts_at']),
            models.Index(fields=['target_audience']),
            models.Index(fields=['announcement_type']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_announcement_type_display()})"
    
    def is_visible_now(self):
        """Check if announcement should be visible now"""
        now = timezone.now()
        if not self.is_active or now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True
    
    def get_type_class(self):
        """Return CSS class for announcement type"""
        classes = {
            'info': 'info',
            'warning': 'warning',
            'maintenance': 'danger',
            'feature': 'success',
            'policy': 'primary',
            'celebration': 'warning'
        }
        return classes.get(self.announcement_type, 'secondary')
