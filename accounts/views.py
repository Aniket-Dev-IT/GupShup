from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, UpdateView
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from .forms import (
    GupShupRegistrationForm, GupShupLoginForm, 
    ProfileCompletionForm, PasswordResetRequestForm
)
from .models import GupShupUser
import json


def home_view(request):
    """
    Home page - redirect to feed if logged in, else show welcome page
    """
    if request.user.is_authenticated:
        return redirect('posts:feed')  # Will create this later
    
    return render(request, 'accounts/welcome.html')


def register_view(request):
    """
    User registration with Indian context
    """
    if request.user.is_authenticated:
        return redirect('accounts:profile_completion')
    
    if request.method == 'POST':
        form = GupShupRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Authenticate and login the user
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            
            if user:
                login(request, user)
                messages.success(
                    request, 
                    f'Welcome to GupShup, {user.get_display_name()}! 🎉'
                )
                
                # Check if profile needs completion
                if not user.bio and not user.avatar:
                    return redirect('accounts:profile_completion')
                else:
                    return redirect('accounts:profile')
            else:
                messages.error(request, 'Registration successful but login failed.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = GupShupRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Join GupShup - Connect with India 🇮🇳'
    }
    return render(request, 'accounts/register.html', context)


def login_view(request):
    """
    User login supporting email, phone, or username
    """
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = GupShupLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Handle remember me
            if form.cleaned_data.get('remember_me'):
                request.session.set_expiry(30 * 24 * 60 * 60)  # 30 days
            else:
                request.session.set_expiry(0)  # Browser session
            
            messages.success(
                request, 
                f'Welcome back, {user.get_display_name()}! 👋'
            )
            
            # Redirect to next page or profile
            next_page = request.GET.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect('accounts:profile')
        else:
            messages.error(request, 'Invalid credentials. Please try again.')
    else:
        form = GupShupLoginForm()
    
    context = {
        'form': form,
        'title': 'Login to GupShup'
    }
    return render(request, 'accounts/login.html', context)


@login_required
def logout_view(request):
    """
    User logout
    """
    user_name = request.user.get_display_name()
    logout(request)
    messages.success(request, f'Goodbye, {user_name}! See you soon on GupShup! 👋')
    return redirect('accounts:home')


@login_required
def profile_view(request):
    """
    User profile view
    """
    user = request.user
    context = {
        'user': user,
        'title': f'{user.get_display_name()} - Profile'
    }
    return render(request, 'accounts/profile.html', context)


@method_decorator(login_required, name='dispatch')
class ProfileCompletionView(UpdateView):
    """
    Profile completion after registration
    """
    model = GupShupUser
    form_class = ProfileCompletionForm
    template_name = 'accounts/profile_completion.html'
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            'Profile updated successfully! Welcome to the GupShup community! 🎉'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Complete Your Profile'
        return context


@method_decorator(login_required, name='dispatch')
class ProfileEditView(UpdateView):
    """
    Edit user profile
    """
    model = GupShupUser
    form_class = ProfileCompletionForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Profile'
        return context


def check_username_availability(request):
    """
    AJAX view to check username availability
    """
    username = request.GET.get('username', '').strip()
    
    if not username:
        return JsonResponse({'available': False, 'message': 'Username is required'})
    
    # Check if username exists
    exists = GupShupUser.objects.filter(username=username).exists()
    
    if exists:
        return JsonResponse({
            'available': False, 
            'message': 'This username is already taken'
        })
    
    # Check if username looks like email or phone
    if '@' in username:
        return JsonResponse({
            'available': False, 
            'message': 'Username cannot be an email address'
        })
    
    import re
    if re.match(r'^[\d+\-\s()]+$', username):
        return JsonResponse({
            'available': False, 
            'message': 'Username cannot be a phone number'
        })
    
    return JsonResponse({
        'available': True, 
        'message': 'Username is available! ✓'
    })


def check_email_availability(request):
    """
    AJAX view to check email availability
    """
    email = request.GET.get('email', '').strip()
    
    if not email:
        return JsonResponse({'available': False, 'message': 'Email is required'})
    
    exists = GupShupUser.objects.filter(email=email).exists()
    
    if exists:
        return JsonResponse({
            'available': False, 
            'message': 'This email is already registered'
        })
    
    return JsonResponse({
        'available': True, 
        'message': 'Email is available! ✓'
    })


def check_phone_availability(request):
    """
    AJAX view to check phone number availability
    """
    phone = request.GET.get('phone', '').strip()
    
    if not phone:
        return JsonResponse({'available': True, 'message': 'Phone number is optional'})
    
    # Normalize phone number
    from .backends import EmailOrPhoneBackend
    backend = EmailOrPhoneBackend()
    phone_normalized = backend._normalize_indian_phone(phone)
    
    if not phone_normalized:
        return JsonResponse({
            'available': False, 
            'message': 'Please enter a valid Indian phone number (+91)'
        })
    
    exists = GupShupUser.objects.filter(phone_number=phone_normalized).exists()
    
    if exists:
        return JsonResponse({
            'available': False, 
            'message': 'This phone number is already registered'
        })
    
    return JsonResponse({
        'available': True, 
        'message': 'Phone number is available! ✓'
    })


def password_reset_request(request):
    """
    Request password reset via email or phone
    """
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['email_or_phone']
            
            # TODO: Implement actual password reset logic
            # For now, just show a success message
            messages.success(
                request, 
                f'Password reset instructions have been sent to your registered contact method.'
            )
            return redirect('accounts:login')
    else:
        form = PasswordResetRequestForm()
    
    context = {
        'form': form,
        'title': 'Reset Password'
    }
    return render(request, 'accounts/password_reset_request.html', context)
