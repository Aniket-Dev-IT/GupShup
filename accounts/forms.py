"""
Custom forms for GupShup authentication
Supports Indian phone numbers, email, and username authentication
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField
import re

User = get_user_model()


class GupShupRegistrationForm(UserCreationForm):
    """
    Registration form with Indian context and phone number support
    """
    
    email = forms.EmailField(
        required=True,
        help_text=_('Enter a valid email address'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com'
        })
    )
    
    phone_number = PhoneNumberField(
        region='IN',
        required=False,
        help_text=_('Indian phone number (+91) - Optional'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+91 9876543210'
        })
    )
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        help_text=_('Your first name'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=False,
        help_text=_('Your last name'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    city = forms.CharField(
        max_length=100,
        required=False,
        help_text=_('Your city (e.g., Mumbai, Delhi, Bangalore)'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your City'
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
        initial='en',
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        help_text=_('I agree to the Terms of Service and Privacy Policy'),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'email', 
            'phone_number', 'city', 'state', 'preferred_language',
            'password1', 'password2'
        )
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Update password field widgets
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
        
        # Update help texts
        self.fields['username'].help_text = _('Letters, digits and @/./+/-/_ only.')
        self.fields['password1'].help_text = _('Your password must contain at least 8 characters.')
    
    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError(_('This email address is already registered.'))
        return email
    
    def clean_phone_number(self):
        """Validate phone number uniqueness and format"""
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            if User.objects.filter(phone_number=phone_number).exists():
                raise ValidationError(_('This phone number is already registered.'))
            
            # Additional validation for Indian numbers
            phone_str = str(phone_number)
            if not phone_str.startswith('+91'):
                raise ValidationError(_('Please enter a valid Indian phone number (+91).'))
        
        return phone_number
    
    def clean_username(self):
        """Validate username uniqueness and format"""
        username = self.cleaned_data.get('username')
        if username:
            # Check if username looks like email or phone
            if '@' in username:
                raise ValidationError(_('Username cannot be an email address.'))
            
            # Check if username looks like phone number
            if re.match(r'^[\d+\-\s()]+$', username):
                raise ValidationError(_('Username cannot be a phone number.'))
            
            # Check uniqueness
            if User.objects.filter(username=username).exists():
                raise ValidationError(_('This username is already taken.'))
        
        return username
    
    def save(self, commit=True):
        """Save user with additional fields"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data.get('phone_number')
        user.city = self.cleaned_data.get('city', '')
        user.state = self.cleaned_data.get('state', '')
        user.preferred_language = self.cleaned_data['preferred_language']
        
        if commit:
            user.save()
        return user


class GupShupLoginForm(AuthenticationForm):
    """
    Custom login form that supports email, phone number, or username
    """
    
    username = forms.CharField(
        label=_('Username, Email or Phone'),
        max_length=254,
        help_text=_('You can login with username, email, or phone number (+91)'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username, Email or +91 Phone Number',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Remember me for 30 days')
    )
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username is not None and password:
            # Use our custom backend for authentication
            self.user_cache = authenticate(
                self.request, 
                username=username, 
                password=password
            )
            
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)
        
        return self.cleaned_data
    
    def get_invalid_login_error(self):
        return ValidationError(
            _('Please enter a correct username/email/phone and password. '
              'Note that both fields may be case-sensitive.'),
            code='invalid_login'
        )


class ProfileCompletionForm(forms.ModelForm):
    """
    Form for completing user profile after registration
    """
    
    bio = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Tell us about yourself...',
            'rows': 3
        }),
        help_text=_('Tell others about yourself (500 characters max)')
    )
    
    avatar = forms.ImageField(
        required=False,
        help_text=_('Upload a profile picture (JPG, PNG)'),
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    date_of_birth = forms.DateField(
        required=False,
        help_text=_('Your date of birth (will not be public)'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    class Meta:
        model = User
        fields = ['bio', 'avatar', 'date_of_birth', 'city', 'state']
        widgets = {
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your city'
            }),
            'state': forms.Select(attrs={
                'class': 'form-control'
            })
        }
    
    def clean_avatar(self):
        """Validate avatar image"""
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            # Check file size (max 5MB)
            if avatar.size > 5 * 1024 * 1024:
                raise ValidationError(_('Image file too large (max 5MB).'))
            
            # Check file type
            if not avatar.content_type.startswith('image/'):
                raise ValidationError(_('Please upload a valid image file.'))
        
        return avatar


class PasswordResetRequestForm(forms.Form):
    """
    Password reset form that accepts email or phone number
    """
    
    email_or_phone = forms.CharField(
        label=_('Email or Phone Number'),
        max_length=254,
        help_text=_('Enter your email address or phone number (+91)'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email or +91 Phone Number'
        })
    )
    
    def clean_email_or_phone(self):
        """Find user by email or phone"""
        identifier = self.cleaned_data['email_or_phone'].strip()
        
        user = None
        
        # Try email first
        if '@' in identifier:
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                pass
        
        # Try phone number
        if not user and (identifier.startswith('+91') or identifier.isdigit()):
            # Normalize phone number
            from .backends import EmailOrPhoneBackend
            backend = EmailOrPhoneBackend()
            phone_normalized = backend._normalize_indian_phone(identifier)
            
            if phone_normalized:
                try:
                    user = User.objects.get(phone_number=phone_normalized)
                except User.DoesNotExist:
                    pass
        
        if not user:
            raise ValidationError(_('No account found with this email or phone number.'))
        
        return user