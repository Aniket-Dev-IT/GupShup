"""
Views for static pages (Help Center, Privacy Policy, Terms, etc.)
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from posts.models import Post
from accounts.models import GupShupUser


def home_view(request):
    """Homepage view - shows welcome page for anonymous users or redirects to feed for authenticated users"""
    if request.user.is_authenticated:
        # Redirect authenticated users to their feed
        from django.shortcuts import redirect
        return redirect('posts:feed')
    
    # Show landing page for anonymous users
    context = {
        'title': 'Welcome to GupShup - Connect with India! 🇮🇳',
        'recent_posts_count': Post.objects.filter(privacy='public').count(),
        'user_count': GupShupUser.objects.count(),
    }
    return render(request, 'pages/home.html', context)


def help_center_view(request):
    """Help Center page with FAQ and support information"""
    context = {
        'title': 'Help Center - GupShup'
    }
    return render(request, 'pages/help_center.html', context)


def privacy_policy_view(request):
    """Privacy Policy page"""
    context = {
        'title': 'Privacy Policy - GupShup'
    }
    return render(request, 'pages/privacy_policy.html', context)


def terms_of_service_view(request):
    """Terms of Service page"""
    context = {
        'title': 'Terms of Service - GupShup'
    }
    return render(request, 'pages/terms_of_service.html', context)


def contact_us_view(request):
    """Contact Us page"""
    context = {
        'title': 'Contact Us - GupShup'
    }
    return render(request, 'pages/contact_us.html', context)


def community_guidelines_view(request):
    """Community Guidelines page"""
    context = {
        'title': 'Community Guidelines - GupShup'
    }
    return render(request, 'pages/community_guidelines.html', context)


def cookie_policy_view(request):
    """Cookie Policy page"""
    context = {
        'title': 'Cookie Policy - GupShup'
    }
    return render(request, 'pages/cookie_policy.html', context)


def data_protection_view(request):
    """Data Protection page"""
    context = {
        'title': 'Data Protection - GupShup'
    }
    return render(request, 'pages/data_protection.html', context)


def features_view(request):
    """Features page showcasing GupShup's key features"""
    context = {
        'title': 'Features - GupShup',
        'user_count': GupShupUser.objects.count(),
        'posts_count': Post.objects.count(),
    }
    return render(request, 'pages/features.html', context)


def community_view(request):
    """Community page showcasing GupShup's community"""
    context = {
        'title': 'Community - GupShup',
        'user_count': GupShupUser.objects.count(),
        'recent_users': GupShupUser.objects.filter(is_active=True).order_by('-date_joined')[:6],
        'recent_posts_count': Post.objects.filter(privacy='public').count(),
    }
    return render(request, 'pages/community.html', context)
