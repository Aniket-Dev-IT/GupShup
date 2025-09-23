from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from PIL import Image
import uuid


def post_media_path(instance, filename):
    """Generate upload path for post media"""
    return f'posts/{instance.post.author.username}/{uuid.uuid4().hex[:8]}_{filename}'


class Post(models.Model):
    """
    Post model for GupShup - Indian Social Media Platform
    
    Supports text posts, image posts, and mixed content
    with Indian cultural context and hashtags
    """
    
    PRIVACY_CHOICES = [
        ('public', _('Public')),
        ('friends', _('Friends Only')),
        ('private', _('Only Me')),
    ]
    
    # Core Post Fields
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posts',
        help_text=_('Post author')
    )
    
    content = models.TextField(
        max_length=2000,
        blank=True,
        help_text=_('What\'s on your mind? (supports Hindi and English)')
    )
    
    # Privacy and Visibility
    privacy = models.CharField(
        max_length=10,
        choices=PRIVACY_CHOICES,
        default='public',
        help_text=_('Who can see this post?')
    )
    
    # Location (Indian context)
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text=_('Add location (e.g., Mumbai, Maharashtra)')
    )
    
    # Hashtags (will be extracted from content)
    hashtags = models.TextField(
        blank=True,
        help_text=_('Extracted hashtags from post')
    )
    
    # Engagement Metrics
    likes_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of likes')
    )
    
    comments_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of comments')
    )
    
    shares_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of shares')
    )
    
    views_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of views')
    )
    
    # Flags
    is_pinned = models.BooleanField(
        default=False,
        help_text=_('Pinned post (appears at top of profile)')
    )
    
    is_edited = models.BooleanField(
        default=False,
        help_text=_('Post has been edited')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        db_table = 'gupshup_posts'
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['privacy']),
            models.Index(fields=['location']),
        ]
    
    def __str__(self):
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"@{self.author.username}: {content_preview}"
    
    def save(self, *args, **kwargs):
        """Override save to extract hashtags"""
        # Extract hashtags from content
        import re
        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, self.content)
        self.hashtags = ','.join(hashtags) if hashtags else ''
        
        # Set is_edited if this is an update
        if self.pk and 'update_fields' not in kwargs:
            self.is_edited = True
        
        super().save(*args, **kwargs)
    
    def get_hashtag_list(self):
        """Return list of hashtags"""
        return self.hashtags.split(',') if self.hashtags else []
    
    def get_absolute_url(self):
        """Return URL for this post"""
        from django.urls import reverse
        return reverse('posts:detail', kwargs={'pk': self.pk})


class PostMedia(models.Model):
    """
    Media files associated with posts
    Supports images and videos
    """
    
    MEDIA_TYPES = [
        ('image', _('Image')),
        ('video', _('Video')),
    ]
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='media_files',
        help_text=_('Associated post')
    )
    
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPES,
        default='image'
    )
    
    file = models.FileField(
        upload_to=post_media_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi']
            )
        ],
        help_text=_('Upload image or video')
    )
    
    caption = models.CharField(
        max_length=200,
        blank=True,
        help_text=_('Media caption')
    )
    
    order = models.PositiveIntegerField(
        default=0,
        help_text=_('Display order')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        db_table = 'gupshup_post_media'
        verbose_name = _('Post Media')
        verbose_name_plural = _('Post Media')
        ordering = ['order']
        indexes = [
            models.Index(fields=['post', 'order']),
            models.Index(fields=['media_type']),
        ]
    
    def __str__(self):
        return f"{self.media_type} for {self.post.author.username}'s post"
    
    def save(self, *args, **kwargs):
        """Override save to handle image compression"""
        super().save(*args, **kwargs)
        
        # Compress images
        if self.media_type == 'image' and self.file:
            try:
                img = Image.open(self.file.path)
                if img.height > 1080 or img.width > 1080:
                    output_size = (1080, 1080)
                    img.thumbnail(output_size, Image.Resampling.LANCZOS)
                    img.save(self.file.path, optimize=True, quality=85)
            except Exception as e:
                # Log error but don't fail the save
                pass
