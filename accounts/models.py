from django.db import models
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField
from PIL import Image
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class GupShupUser(AbstractUser):
    """
    User model for GupShup - Indian Social Media Platform
    
    Extends Django's AbstractUser to include Indian-specific fields
    and social media features
    """
    
    # Basic Indian Context Fields
    phone_number = PhoneNumberField(
        region='IN',
        help_text=_('Indian phone number (+91)'),
        blank=True,
        null=True,
        unique=True
    )
    
    # Profile Fields
    bio = models.TextField(
        max_length=500,
        blank=True,
        help_text=_('Tell us about yourself')
    )
    
    # Location - Indian cities/states focus
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Your city (e.g., Mumbai, Delhi, Bangalore)')
    )
    
    state = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('AN', 'Andaman and Nicobar Islands'),
            ('AP', 'Andhra Pradesh'),
            ('AR', 'Arunachal Pradesh'),
            ('AS', 'Assam'),
            ('BR', 'Bihar'),
            ('CH', 'Chandigarh'),
            ('CG', 'Chhattisgarh'),
            ('DN', 'Dadra and Nagar Haveli'),
            ('DD', 'Daman and Diu'),
            ('DL', 'Delhi'),
            ('GA', 'Goa'),
            ('GJ', 'Gujarat'),
            ('HR', 'Haryana'),
            ('HP', 'Himachal Pradesh'),
            ('JK', 'Jammu and Kashmir'),
            ('JH', 'Jharkhand'),
            ('KA', 'Karnataka'),
            ('KL', 'Kerala'),
            ('LD', 'Lakshadweep'),
            ('MP', 'Madhya Pradesh'),
            ('MH', 'Maharashtra'),
            ('MN', 'Manipur'),
            ('ML', 'Meghalaya'),
            ('MZ', 'Mizoram'),
            ('NL', 'Nagaland'),
            ('OD', 'Odisha'),
            ('PY', 'Puducherry'),
            ('PB', 'Punjab'),
            ('RJ', 'Rajasthan'),
            ('SK', 'Sikkim'),
            ('TN', 'Tamil Nadu'),
            ('TS', 'Telangana'),
            ('TR', 'Tripura'),
            ('UP', 'Uttar Pradesh'),
            ('UK', 'Uttarakhand'),
            ('WB', 'West Bengal'),
        ]
    )
    
    # Language preferences
    preferred_language = models.CharField(
        max_length=5,
        default='en',
        choices=[
            ('en', 'English'),
            ('hi', 'हिन्दी'),  # Hindi
            # More languages can be added
        ],
        help_text=_('Your preferred language for GupShup')
    )
    
    # Avatar/Profile Picture
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text=_('Profile picture')
    )
    
    # Social Media Fields
    is_verified = models.BooleanField(
        default=False,
        help_text=_('Verified account badge')
    )
    
    followers_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of followers')
    )
    
    following_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of people user is following')
    )
    
    posts_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of posts by user')
    )
    
    # Privacy Settings
    is_private = models.BooleanField(
        default=False,
        help_text=_('Private account - requires approval for follow')
    )
    
    # Timestamps
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text=_('Your date of birth')
    )
    
    last_seen = models.DateTimeField(
        auto_now=True,
        help_text=_('Last activity timestamp')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        db_table = 'gupshup_users'
        verbose_name = _('GupShup User')
        verbose_name_plural = _('GupShup Users')
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['city', 'state']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_seen']),
        ]
    
    def __str__(self):
        return f"@{self.username} ({self.get_full_name() or self.email})"
    
    def get_display_name(self):
        """Return full name or username for display"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return f"@{self.username}"
    
    def get_avatar_url(self):
        """Return avatar URL or default"""
        if self.avatar and hasattr(self.avatar, 'url'):
            try:
                # Try to access the URL - this will raise an exception if file doesn't exist
                url = self.avatar.url
                return url
            except (ValueError, FileNotFoundError):
                # File doesn't exist or has no file associated
                return '/static/img/default-avatar.svg'
        # Return default avatar 
        return '/static/img/default-avatar.svg'
    
    def save(self, *args, **kwargs):
        """Override save to handle image compression"""
        super().save(*args, **kwargs)
        
        # Compress avatar image
        if self.avatar:
            try:
                img = Image.open(self.avatar.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.avatar.path)
            except Exception as e:
                # Log error but don't fail the save
                pass
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        # Validate phone number is Indian
        if self.phone_number and not str(self.phone_number).startswith('+91'):
            raise ValidationError({'phone_number': _('Please enter a valid Indian phone number (+91)')})
