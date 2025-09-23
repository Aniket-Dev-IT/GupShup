"""
Forms for GupShup Social Features
Handles user search, friend requests, and social interactions
"""

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

User = get_user_model()


class UserSearchForm(forms.Form):
    """
    Form for searching users with various filters
    """
    
    SEARCH_TYPE_CHOICES = [
        ('all', _('All Users')),
        ('name', _('By Name')),
        ('username', _('By Username')),
        ('location', _('By Location')),
        ('language', _('By Language')),
    ]
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search users by name, username, location... (Hindi/English supported)',
            'autocomplete': 'off'
        }),
        help_text=_('Search for people on GupShup')
    )
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPE_CHOICES,
        initial='all',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text=_('Filter search results')
    )
    
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by city (e.g., Mumbai, Delhi)',
            'list': 'indian-cities'
        }),
        help_text=_('Find people from specific cities')
    )
    
    state = forms.ChoiceField(
        choices=[('', 'All States')] + [
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
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    language = forms.ChoiceField(
        choices=[
            ('', 'All Languages'),
            ('en', 'English'),
            ('hi', 'हिन्दी (Hindi)'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def clean_query(self):
        """Clean and validate search query"""
        query = self.cleaned_data.get('query', '').strip()
        
        if query:
            # Remove excessive whitespace
            query = ' '.join(query.split())
            
            # Basic validation
            if len(query) < 2:
                raise ValidationError(_('Search query must be at least 2 characters long.'))
        
        return query
    
    def search_users(self, exclude_user=None):
        """
        Perform user search based on form data
        """
        query = self.cleaned_data.get('query', '')
        search_type = self.cleaned_data.get('search_type', 'all')
        city = self.cleaned_data.get('city', '')
        state = self.cleaned_data.get('state', '')
        language = self.cleaned_data.get('language', '')
        
        # Start with active users
        users = User.objects.filter(is_active=True)
        
        # Exclude current user if provided
        if exclude_user:
            users = users.exclude(pk=exclude_user.pk)
        
        # Apply search query
        if query:
            if search_type == 'name':
                users = users.filter(
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query)
                )
            elif search_type == 'username':
                users = users.filter(username__icontains=query)
            elif search_type == 'location':
                users = users.filter(
                    Q(city__icontains=query) |
                    Q(state__icontains=query)
                )
            else:  # 'all'
                users = users.filter(
                    Q(username__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query) |
                    Q(city__icontains=query) |
                    Q(bio__icontains=query)
                )
        
        # Apply filters
        if city:
            users = users.filter(city__icontains=city)
        
        if state:
            users = users.filter(state=state)
        
        if language:
            users = users.filter(preferred_language=language)
        
        return users.select_related().order_by('-date_joined')


class FollowActionForm(forms.Form):
    """
    Form for follow/unfollow actions
    """
    
    ACTION_CHOICES = [
        ('follow', 'Follow'),
        ('unfollow', 'Unfollow'),
        ('accept', 'Accept Request'),
        ('reject', 'Reject Request'),
        ('cancel', 'Cancel Request'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.HiddenInput()
    )
    
    user_id = forms.IntegerField(
        widget=forms.HiddenInput()
    )
    
    def clean_user_id(self):
        """Validate user exists"""
        user_id = self.cleaned_data.get('user_id')
        
        try:
            user = User.objects.get(pk=user_id, is_active=True)
            return user_id
        except User.DoesNotExist:
            raise ValidationError(_('User not found.'))


class ReportUserForm(forms.Form):
    """
    Form for reporting users
    """
    
    REPORT_REASONS = [
        ('spam', _('Spam')),
        ('harassment', _('Harassment')),
        ('inappropriate', _('Inappropriate Content')),
        ('fake', _('Fake Profile')),
        ('other', _('Other')),
    ]
    
    reason = forms.ChoiceField(
        choices=REPORT_REASONS,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text=_('Why are you reporting this user?')
    )
    
    description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Please provide additional details (optional)',
            'rows': 3
        }),
        help_text=_('Additional details about the report')
    )
    
    def clean_description(self):
        """Clean report description"""
        description = self.cleaned_data.get('description', '').strip()
        
        # Remove excessive whitespace
        if description:
            description = ' '.join(description.split())
        
        return description


class UserProfileUpdateForm(forms.ModelForm):
    """
    Extended form for updating user profile
    """
    
    bio = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Tell the world about yourself... (Hindi/English supported) 🇮🇳',
            'rows': 4
        }),
        help_text=_('Share your story, interests, and what makes you unique')
    )
    
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your city (e.g., Mumbai, Delhi, Bangalore)',
            'list': 'indian-cities'
        })
    )
    
    state = forms.ChoiceField(
        choices=[('', 'Select State')] + [
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
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    preferred_language = forms.ChoiceField(
        choices=[
            ('en', 'English'),
            ('hi', 'हिन्दी (Hindi)'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    avatar = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text=_('Upload a profile picture (JPG, PNG - max 5MB)')
    )
    
    is_private = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text=_('Make your profile private (followers need approval)')
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'bio', 'city', 'state', 
                 'preferred_language', 'avatar', 'is_private']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
        }
    
    def clean_avatar(self):
        """Validate avatar upload"""
        avatar = self.cleaned_data.get('avatar')
        
        if avatar:
            # Check file size (max 5MB)
            if avatar.size > 5 * 1024 * 1024:
                raise ValidationError(_('Image file too large. Maximum size is 5MB.'))
            
            # Check file type
            if not avatar.content_type.startswith('image/'):
                raise ValidationError(_('Please upload a valid image file.'))
        
        return avatar
    
    def clean_bio(self):
        """Clean and validate bio"""
        bio = self.cleaned_data.get('bio', '').strip()
        
        if bio:
            # Remove excessive whitespace
            bio = ' '.join(bio.split())
            
            # Check for spam (excessive hashtags or mentions)
            hashtags = bio.count('#')
            mentions = bio.count('@')
            
            if hashtags > 5:
                raise ValidationError(_('Too many hashtags in bio. Maximum 5 allowed.'))
            
            if mentions > 3:
                raise ValidationError(_('Too many mentions in bio. Maximum 3 allowed.'))
        
        return bio