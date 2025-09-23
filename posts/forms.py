"""
Forms for GupShup Posts with Indian context
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Post, PostMedia
from social.models import Comment
import re


class PostCreationForm(forms.ModelForm):
    """
    Form for creating new posts with text and media support
    """
    
    content = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Share your thoughts... Express yourself in Hindi or English! 🇮🇳\n\nUse #hashtags to reach more people\nTag your location to connect locally',
            'rows': 4,
            'style': 'resize: vertical;'
        }),
        help_text=_('Share what\'s on your mind (supports Hindi and English)')
    )
    
    location = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Add location (e.g., Mumbai, Maharashtra)',
            'list': 'indian-cities'
        }),
        help_text=_('Tag your location to connect with local community')
    )
    
    privacy = forms.ChoiceField(
        choices=Post.PRIVACY_CHOICES,
        initial='public',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text=_('Who can see this post?')
    )
    
    # Media upload field for images and videos
    media_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,video/*'
        }),
        help_text=_('Upload an image or video (JPG, PNG, GIF, MP4, MOV)')
    )
    
    class Meta:
        model = Post
        fields = ['content', 'location', 'privacy']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Add Indian cities datalist for location autocomplete
        indian_cities = [
            'Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Kolkata', 'Hyderabad',
            'Pune', 'Ahmedabad', 'Surat', 'Jaipur', 'Lucknow', 'Kanpur',
            'Nagpur', 'Indore', 'Thane', 'Bhopal', 'Visakhapatnam', 'Patna',
            'Vadodara', 'Ludhiana', 'Agra', 'Nashik', 'Faridabad', 'Meerut',
            'Rajkot', 'Kalyan-Dombivali', 'Vasai-Virar', 'Varanasi', 'Srinagar',
            'Aurangabad', 'Dhanbad', 'Amritsar', 'Navi Mumbai', 'Allahabad',
            'Howrah', 'Gwalior', 'Jabalpur', 'Coimbatore', 'Vijayawada'
        ]
        self.indian_cities = indian_cities
    
    def clean_content(self):
        """Validate post content"""
        content = self.cleaned_data.get('content', '').strip()
        
        # Check if post is completely empty
        if not content and not self.files.get('media_file'):
            raise ValidationError(_('Post cannot be empty. Add some text or media.'))
        
        # Check for spam (excessive hashtags)
        hashtags = re.findall(r'#\w+', content)
        if len(hashtags) > 10:
            raise ValidationError(_('Too many hashtags! Please use maximum 10 hashtags.'))
        
        # Check for spam (excessive mentions)
        mentions = re.findall(r'@\w+', content)
        if len(mentions) > 5:
            raise ValidationError(_('Too many mentions! Please mention maximum 5 users.'))
        
        return content
    
    def clean_media_file(self):
        """Validate uploaded media file"""
        media_file = self.cleaned_data.get('media_file')
        
        if media_file:
            # Check file size (max 50MB for videos, 10MB for images)
            max_size = 50 * 1024 * 1024 if media_file.content_type.startswith('video/') else 10 * 1024 * 1024
            if media_file.size > max_size:
                size_label = '50MB' if media_file.content_type.startswith('video/') else '10MB'
                raise ValidationError(f'{media_file.name} is too large. Maximum size is {size_label}.')
            
            # Check file type
            if not (media_file.content_type.startswith('image/') or media_file.content_type.startswith('video/')):
                raise ValidationError(f'{media_file.name} is not a valid image or video file.')
            
            # Additional video validation
            if media_file.content_type.startswith('video/'):
                allowed_video_types = ['video/mp4', 'video/quicktime', 'video/x-msvideo']
                if media_file.content_type not in allowed_video_types:
                    raise ValidationError('Only MP4, MOV, and AVI video formats are supported.')
        
        return media_file
    
    def save(self, commit=True):
        """Save post with author"""
        post = super().save(commit=False)
        if self.user:
            post.author = self.user
        
        if commit:
            post.save()
            
            # Handle media file upload
            media_file = self.cleaned_data.get('media_file')
            if media_file:
                # Determine media type
                media_type = 'video' if media_file.content_type.startswith('video/') else 'image'
                PostMedia.objects.create(
                    post=post,
                    file=media_file,
                    media_type=media_type,
                    order=0
                )
        
        return post


class CommentForm(forms.ModelForm):
    """
    Form for creating comments on posts
    """
    
    content = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Write a comment... (Hindi/English supported) 💬',
            'rows': 2,
            'style': 'resize: vertical;'
        }),
        help_text=_('Share your thoughts (500 characters max)')
    )
    
    class Meta:
        model = Comment
        fields = ['content']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.post = kwargs.pop('post', None)
        self.parent_comment = kwargs.pop('parent_comment', None)
        super().__init__(*args, **kwargs)
    
    def clean_content(self):
        """Validate comment content"""
        content = self.cleaned_data.get('content', '').strip()
        
        if not content:
            raise ValidationError(_('Comment cannot be empty.'))
        
        # Check for spam (excessive mentions)
        mentions = re.findall(r'@\w+', content)
        if len(mentions) > 3:
            raise ValidationError(_('Too many mentions! Please mention maximum 3 users.'))
        
        return content
    
    def save(self, commit=True):
        """Save comment with required relationships"""
        comment = super().save(commit=False)
        
        if self.user:
            comment.author = self.user
        if self.post:
            comment.post = self.post
        if self.parent_comment:
            comment.parent_comment = self.parent_comment
        
        if commit:
            comment.save()
        
        return comment


class PostEditForm(forms.ModelForm):
    """
    Enhanced form for editing existing posts with media support
    """
    
    content = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'style': 'resize: vertical;',
            'placeholder': 'Update your post content...'
        }),
        help_text=_('Update your post content (supports Hindi and English)')
    )
    
    location = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Update location (e.g., Mumbai, Maharashtra)',
            'list': 'indian-cities'
        }),
        help_text=_('Update your location')
    )
    
    privacy = forms.ChoiceField(
        choices=Post.PRIVACY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text=_('Update who can see this post')
    )
    
    # New media fields for editing
    new_media_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,video/*',
            'multiple': False
        }),
        help_text=_('Upload new image or video to replace existing media (optional)')
    )
    
    remove_media = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text=_('Check this to remove all existing media files')
    )
    
    class Meta:
        model = Post
        fields = ['content', 'location', 'privacy']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate form with existing data
        if self.instance and self.instance.pk:
            # Add information about existing media
            media_count = self.instance.media_files.count()
            if media_count > 0:
                media_type = 'image' if self.instance.media_files.first().media_type == 'image' else 'video'
                self.fields['new_media_file'].help_text = f'Currently has {media_count} {media_type}(s). Upload new file to replace all existing media.'
    
    def clean_content(self):
        """Validate updated content"""
        content = self.cleaned_data.get('content', '').strip()
        
        # Check if post will be completely empty after edit
        remove_media = self.cleaned_data.get('remove_media', False)
        new_media = self.cleaned_data.get('new_media_file')
        has_existing_media = self.instance.media_files.exists() if self.instance else False
        
        # Post must have either content or media
        if not content:
            if remove_media and not new_media:
                raise ValidationError(_('Post cannot be empty. Add some text or media.'))
            elif not has_existing_media and not new_media:
                raise ValidationError(_('Post cannot be empty. Add some text or media.'))
        
        return content
    
    def clean_new_media_file(self):
        """Validate new media file"""
        media_file = self.cleaned_data.get('new_media_file')
        
        if media_file:
            # Check file size (max 50MB for videos, 10MB for images)
            max_size = 50 * 1024 * 1024 if media_file.content_type.startswith('video/') else 10 * 1024 * 1024
            if media_file.size > max_size:
                size_label = '50MB' if media_file.content_type.startswith('video/') else '10MB'
                raise ValidationError(f'File is too large. Maximum size is {size_label}.')
            
            # Check file type
            if not (media_file.content_type.startswith('image/') or media_file.content_type.startswith('video/')):
                raise ValidationError('Please upload a valid image or video file.')
        
        return media_file
    
    def save(self, commit=True):
        """Save post with media handling"""
        post = super().save(commit=commit)
        
        if commit:
            # Handle media removal
            if self.cleaned_data.get('remove_media', False):
                post.media_files.all().delete()
            
            # Handle new media upload
            new_media = self.cleaned_data.get('new_media_file')
            if new_media:
                # Remove existing media if new media is uploaded
                post.media_files.all().delete()
                
                # Add new media
                media_type = 'video' if new_media.content_type.startswith('video/') else 'image'
                PostMedia.objects.create(
                    post=post,
                    file=new_media,
                    media_type=media_type,
                    order=0
                )
        
        return post


class HashtagSearchForm(forms.Form):
    """
    Form for searching posts by hashtags
    """
    
    hashtag = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search hashtags (e.g., Mumbai, Cricket, Bollywood)',
            'autocomplete': 'off'
        }),
        help_text=_('Search for popular hashtags and topics')
    )
    
    def clean_hashtag(self):
        """Clean and validate hashtag"""
        hashtag = self.cleaned_data.get('hashtag', '').strip()
        
        # Remove # if user added it
        if hashtag.startswith('#'):
            hashtag = hashtag[1:]
        
        # Validate hashtag format
        if not re.match(r'^[a-zA-Z0-9_\u0900-\u097F]+$', hashtag):
            raise ValidationError(_('Hashtag can only contain letters, numbers, and underscores.'))
        
        return hashtag


class PostSearchForm(forms.Form):
    """
    Form for searching posts with multiple filters
    """
    
    SEARCH_CHOICES = [
        ('all', _('All Posts')),
        ('text', _('Text Only')),
        ('media', _('With Images')),
        ('location', _('With Location')),
    ]
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search posts, hashtags, locations... (Hindi/English)',
        })
    )
    
    search_type = forms.ChoiceField(
        choices=SEARCH_CHOICES,
        initial='all',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    location = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by location'
        })
    )
    
    def clean_query(self):
        """Clean search query"""
        query = self.cleaned_data.get('query', '').strip()
        
        # Remove excessive whitespace
        query = ' '.join(query.split())
        
        return query