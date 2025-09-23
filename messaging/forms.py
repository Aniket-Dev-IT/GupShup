"""
Forms for GupShup Messaging System
Handles message creation and conversation management
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Message, Conversation


class MessageForm(forms.ModelForm):
    """
    Form for sending messages
    """
    class Meta:
        model = Message
        fields = ['content', 'image', 'file']
        widgets = {
            'content': forms.Textarea(
                attrs={
                    'class': 'form-control message-input',
                    'placeholder': 'Type your message here... 💬',
                    'rows': 3,
                    'maxlength': 2000,
                    'style': 'resize: none; border-radius: 20px;'
                }
            ),
            'image': forms.FileInput(
                attrs={
                    'class': 'form-control d-none',
                    'accept': 'image/*',
                    'id': 'message-image-input'
                }
            ),
            'file': forms.FileInput(
                attrs={
                    'class': 'form-control d-none',
                    'accept': '.pdf,.doc,.docx,.txt,.zip,.rar',
                    'id': 'message-file-input'
                }
            ),
        }
    
    def clean_content(self):
        """
        Validate message content
        """
        content = self.cleaned_data.get('content', '').strip()
        
        # Allow empty content if there's an image or file
        if not content and not self.cleaned_data.get('image') and not self.cleaned_data.get('file'):
            raise ValidationError("Please enter a message or attach an image/file.")
        
        if len(content) > 2000:
            raise ValidationError("Message is too long. Maximum 2000 characters allowed.")
        
        return content
    
    def clean_image(self):
        """
        Validate uploaded image
        """
        image = self.cleaned_data.get('image')
        
        if image:
            # Check file size (max 5MB)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError("Image size must be less than 5MB.")
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(image, 'content_type') and image.content_type not in allowed_types:
                raise ValidationError("Please upload a valid image file (JPEG, PNG, GIF, WebP).")
        
        return image
    
    def clean_file(self):
        """
        Validate uploaded file
        """
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size must be less than 10MB.")
            
            # Check file type
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.zip', '.rar']
            file_name = file.name.lower()
            
            if not any(file_name.endswith(ext) for ext in allowed_extensions):
                raise ValidationError("File type not allowed. Please upload PDF, DOC, DOCX, TXT, ZIP, or RAR files.")
        
        return file
    
    def clean(self):
        """
        Additional validation for the form
        """
        cleaned_data = super().clean()
        content = cleaned_data.get('content', '').strip()
        image = cleaned_data.get('image')
        file = cleaned_data.get('file')
        
        # Ensure at least one field is provided
        if not content and not image and not file:
            raise ValidationError("Please enter a message or attach a file.")
        
        # Don't allow both image and file in same message
        if image and file:
            raise ValidationError("Please send image and file separately.")
        
        return cleaned_data


class QuickMessageForm(forms.Form):
    """
    Quick message form for AJAX requests
    """
    content = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control quick-message-input',
                'placeholder': 'Quick message...',
                'rows': 2,
                'style': 'resize: none;'
            }
        ),
        required=True
    )
    
    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        
        if not content:
            raise ValidationError("Message cannot be empty.")
        
        if len(content) > 2000:
            raise ValidationError("Message too long.")
        
        return content


class ConversationSearchForm(forms.Form):
    """
    Form to search conversations
    """
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Search conversations...',
                'style': 'border-radius: 20px;'
            }
        )
    )
    
    def search_conversations(self, user):
        """
        Search conversations for a user
        """
        query = self.cleaned_data.get('query', '').strip()
        
        if not query:
            return Conversation.get_user_conversations(user)
        
        # Search by other participant's name or username
        conversations = Conversation.get_user_conversations(user)
        
        filtered_conversations = []
        for conv in conversations:
            other_user = conv.get_other_user(user)
            
            # Check if query matches the other user's name or username
            if (query.lower() in other_user.username.lower() or
                query.lower() in other_user.get_display_name().lower()):
                filtered_conversations.append(conv)
        
        return filtered_conversations


class StartConversationForm(forms.Form):
    """
    Form to start a new conversation
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Enter username to message...',
                'style': 'border-radius: 20px;'
            }
        )
    )
    
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'placeholder': 'Type your first message...',
                'rows': 3,
                'style': 'resize: none; border-radius: 15px;'
            }
        ),
        required=False
    )
    
    def clean_username(self):
        """
        Validate the username exists
        """
        from accounts.models import GupShupUser
        
        username = self.cleaned_data.get('username', '').strip()
        
        if not username:
            raise ValidationError("Please enter a username.")
        
        try:
            user = GupShupUser.objects.get(username=username, is_active=True)
        except GupShupUser.DoesNotExist:
            raise ValidationError("User not found or inactive.")
        
        return username
    
    def get_target_user(self):
        """
        Get the target user object
        """
        from accounts.models import GupShupUser
        
        username = self.cleaned_data.get('username')
        if username:
            return GupShupUser.objects.get(username=username, is_active=True)
        return None


class MessageEditForm(forms.ModelForm):
    """
    Form for editing messages (text messages only, within 5 minutes)
    """
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'style': 'resize: none; border-radius: 15px;',
                    'maxlength': 2000
                }
            ),
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        
        if not content:
            raise ValidationError("Message cannot be empty.")
        
        if len(content) > 2000:
            raise ValidationError("Message is too long.")
        
        return content


class ConversationSettingsForm(forms.Form):
    """
    Form for conversation settings (blocking, clearing history, etc.)
    """
    ACTION_CHOICES = [
        ('clear_history', 'Clear Chat History'),
        ('block_user', 'Block User'),
        ('unblock_user', 'Unblock User'),
        ('delete_conversation', 'Delete Conversation'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(
            attrs={'class': 'form-select'}
        )
    )