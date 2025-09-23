from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Exists, OuterRef
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils import timezone
import json
from datetime import datetime, timedelta

from .models import Follow, Like, Comment
from .forms import UserSearchForm, FollowActionForm, ReportUserForm
from accounts.models import GupShupUser
from posts.models import Post


def discover_users_view(request):
    """
    Discover new users - shows trending users, users from same city, etc.
    """
    # Get trending users (users with most recent activity)
    trending_users = GupShupUser.objects.filter(
        is_active=True
    ).annotate(
        post_count=Count('posts'),
        follower_count=Count('followers')
    ).order_by('-follower_count', '-post_count')[:12]
    
    # Get users from same city if user is authenticated
    city_users = []
    if request.user.is_authenticated and request.user.city:
        city_users = GupShupUser.objects.filter(
            city__iexact=request.user.city,
            is_active=True
        ).exclude(id=request.user.id)[:8]
    
    # Get recently joined users
    new_users = GupShupUser.objects.filter(
        is_active=True
    ).order_by('-date_joined')[:8]
    
    # Add follow status for authenticated users
    if request.user.is_authenticated:
        all_users = list(trending_users) + list(city_users) + list(new_users)
        user_ids = [user.id for user in all_users]
        following_ids = set(
            Follow.objects.filter(
                follower=request.user,
                following_id__in=user_ids,
                status='accepted'
            ).values_list('following_id', flat=True)
        )
        
        pending_ids = set(
            Follow.objects.filter(
                follower=request.user,
                following_id__in=user_ids,
                status='pending'
            ).values_list('following_id', flat=True)
        )
        
        for user in all_users:
            user.is_following = user.id in following_ids
            user.is_pending = user.id in pending_ids
    
    context = {
        'trending_users': trending_users,
        'city_users': city_users,
        'new_users': new_users,
        'title': 'Discover People - GupShup'
    }
    
    return render(request, 'social/discover_users.html', context)


def user_search_view(request):
    """
    Search for users with various filters
    """
    form = UserSearchForm(request.GET or None)
    users = []
    query = ''
    
    if form.is_valid():
        query = form.cleaned_data.get('query', '')
        users = form.search_users(exclude_user=request.user if request.user.is_authenticated else None)
        
        # Add follow status for authenticated users
        if request.user.is_authenticated:
            user_ids = [user.id for user in users]
            following_ids = set(
                Follow.objects.filter(
                    follower=request.user,
                    following_id__in=user_ids,
                    status='accepted'
                ).values_list('following_id', flat=True)
            )
            
            pending_ids = set(
                Follow.objects.filter(
                    follower=request.user,
                    following_id__in=user_ids,
                    status='pending'
                ).values_list('following_id', flat=True)
            )
            
            for user in users:
                user.is_following = user.id in following_ids
                user.is_pending = user.id in pending_ids
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get suggested users if no search query
    suggested_users = []
    if not query and request.user.is_authenticated:
        suggested_users = get_suggested_users(request.user)[:6]
    
    context = {
        'form': form,
        'users': page_obj,
        'query': query,
        'suggested_users': suggested_users,
        'title': f'Search: {query}' if query else 'Find People on GupShup'
    }
    
    return render(request, 'social/user_search.html', context)


def user_profile_view(request, username):
    """
    Display user profile with posts, followers, and following
    For admins: show professional admin dashboard instead
    """
    user = get_object_or_404(GupShupUser, username=username, is_active=True)
    
    # Redirect administrators to professional admin dashboard
    if user.is_superuser:
        
        # Get admin dashboard data
        total_users = GupShupUser.objects.count()
        active_users = GupShupUser.objects.filter(is_active=True).count()
        total_posts = Post.objects.count()
        today = timezone.now().date()
        posts_today = Post.objects.filter(created_at__date=today).count()
        recent_users = GupShupUser.objects.order_by('-date_joined')[:5]
        recent_posts = Post.objects.select_related('author').order_by('-created_at')[:5]
        
        admin_context = {
            'admin_user': user,
            'stats': {
                'users': {'total': total_users, 'active': active_users},
                'posts': {'total': total_posts, 'today': posts_today}
            },
            'recent_users': recent_users,
            'recent_posts': recent_posts,
            'today': today
        }
        
        return render(request, 'admin_panel/admin_profile_dashboard.html', admin_context)
    
    # Check if current user can view this profile
    can_view_profile = True
    is_following = False
    is_pending = False
    can_follow = False
    
    if request.user.is_authenticated and user != request.user:
        follow_obj = Follow.objects.filter(follower=request.user, following=user).first()
        if follow_obj:
            is_following = follow_obj.status == 'accepted'
            is_pending = follow_obj.status == 'pending'
        else:
            can_follow = True
        
        # Check if profile is private
        if user.is_private and not is_following:
            can_view_profile = False
    elif not request.user.is_authenticated and user.is_private:
        can_view_profile = False
    
    # Get user's posts if profile is viewable
    posts = []
    if can_view_profile:
        posts = Post.objects.filter(author=user).select_related('author').prefetch_related(
            'media_files', 'likes', 'comments'
        ).order_by('-created_at')
        
        # Filter posts based on privacy
        if request.user != user:
            if request.user.is_authenticated and is_following:
                posts = posts.filter(privacy__in=['public', 'friends'])
            else:
                posts = posts.filter(privacy='public')
    
    # Pagination for posts
    paginator = Paginator(posts, 12)
    page_number = request.GET.get('page')
    posts_page = paginator.get_page(page_number)
    
    # Get follower and following counts
    followers_count = Follow.objects.filter(following=user, status='accepted').count()
    following_count = Follow.objects.filter(follower=user, status='accepted').count()
    
    # Get mutual friends if authenticated
    mutual_friends = []
    if request.user.is_authenticated and user != request.user:
        mutual_friends = get_mutual_friends(request.user, user)[:6]
    
    context = {
        'profile_user': user,
        'posts': posts_page,
        'can_view_profile': can_view_profile,
        'is_following': is_following,
        'is_pending': is_pending,
        'can_follow': can_follow,
        'followers_count': followers_count,
        'following_count': following_count,
        'mutual_friends': mutual_friends,
        'is_own_profile': request.user == user if request.user.is_authenticated else False,
        'title': f'{user.get_display_name()} (@{user.username})'
    }
    
    return render(request, 'social/user_profile.html', context)


@login_required
@require_POST
def follow_action_view(request, username):
    """
    Handle follow/unfollow actions via AJAX
    """
    try:
        target_user = get_object_or_404(GupShupUser, username=username, is_active=True)
        
        if target_user == request.user:
            return JsonResponse({'success': False, 'message': 'Cannot follow yourself'})
        
        follow_obj = Follow.objects.filter(follower=request.user, following=target_user).first()
        
        if follow_obj:
            # Unfollow - delete the relationship
            follow_obj.delete()
            action_taken = 'unfollowed'
            message = 'Unfollowed successfully'
        else:
            # Follow - create the relationship
            is_private = target_user.is_private
            status = 'pending' if is_private else 'accepted'
            Follow.objects.create(
                follower=request.user,
                following=target_user,
                status=status
            )
            action_taken = 'followed'
            message = 'Follow request sent' if status == 'pending' else 'Now following'
        
        # Get updated follow status
        updated_follow = Follow.objects.filter(follower=request.user, following=target_user).first()
        is_following = updated_follow.status == 'accepted' if updated_follow else False
        is_pending = updated_follow.status == 'pending' if updated_follow else False
        
        return JsonResponse({
            'success': True,
            'action': action_taken,
            'message': message,
            'is_following': is_following,
            'is_pending': is_pending,
            'followers_count': Follow.objects.filter(following=target_user, status='accepted').count()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def followers_list_view(request, username):
    """
    List of user's followers
    """
    user = get_object_or_404(GupShupUser, username=username, is_active=True)
    
    # Check permissions
    if user.is_private and user != request.user:
        is_following = Follow.objects.filter(
            follower=request.user, following=user, status='accepted'
        ).exists()
        if not is_following:
            raise Http404('Profile is private')
    
    followers = Follow.objects.filter(
        following=user, status='accepted'
    ).select_related('follower').order_by('-created_at')
    
    # Add follow status for each follower
    if request.user.is_authenticated:
        follower_ids = [f.follower.id for f in followers]
        following_ids = set(
            Follow.objects.filter(
                follower=request.user,
                following_id__in=follower_ids,
                status='accepted'
            ).values_list('following_id', flat=True)
        )
        
        for follow_obj in followers:
            follow_obj.follower.is_following = follow_obj.follower.id in following_ids
    
    paginator = Paginator(followers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'profile_user': user,
        'users': page_obj,  # Template expects 'users'
        'page_obj': page_obj,
        'list_type': 'followers',
        'followers_count': Follow.objects.filter(following=user, status='accepted').count(),
        'following_count': Follow.objects.filter(follower=user, status='accepted').count(),
        'title': f'{user.get_display_name()}\'s Followers'
    }
    
    return render(request, 'social/follow_list.html', context)


@login_required
def following_list_view(request, username):
    """
    List of users that this user is following
    """
    user = get_object_or_404(GupShupUser, username=username, is_active=True)
    
    # Check permissions
    if user.is_private and user != request.user:
        is_following = Follow.objects.filter(
            follower=request.user, following=user, status='accepted'
        ).exists()
        if not is_following:
            raise Http404('Profile is private')
    
    following = Follow.objects.filter(
        follower=user, status='accepted'
    ).select_related('following').order_by('-created_at')
    
    # Add follow status for each following
    if request.user.is_authenticated and request.user != user:
        following_ids = [f.following.id for f in following]
        user_following_ids = set(
            Follow.objects.filter(
                follower=request.user,
                following_id__in=following_ids,
                status='accepted'
            ).values_list('following_id', flat=True)
        )
        
        for follow_obj in following:
            follow_obj.following.is_following = follow_obj.following.id in user_following_ids
    
    paginator = Paginator(following, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'profile_user': user,
        'users': page_obj,  # Template expects 'users'
        'page_obj': page_obj,
        'list_type': 'following',
        'followers_count': Follow.objects.filter(following=user, status='accepted').count(),
        'following_count': Follow.objects.filter(follower=user, status='accepted').count(),
        'title': f'People {user.get_display_name()} Follows'
    }
    
    return render(request, 'social/follow_list.html', context)




@login_required
def suggested_users_view(request):
    """
    Show suggested users to follow
    """
    suggested_users = get_suggested_users(request.user, limit=20)
    
    # Add follow status
    user_ids = [user.id for user in suggested_users]
    following_ids = set(
        Follow.objects.filter(
            follower=request.user,
            following_id__in=user_ids
        ).values_list('following_id', flat=True)
    )
    
    for user in suggested_users:
        user.is_following = user.id in following_ids
    
    paginator = Paginator(suggested_users, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'title': 'Suggested Users'
    }
    
    return render(request, 'social/suggested_users.html', context)


# Helper functions

def get_suggested_users(current_user, limit=10):
    """
    Get suggested users based on various criteria
    """
    # Users current user is already following
    following_ids = Follow.objects.filter(
        follower=current_user
    ).values_list('following_id', flat=True)
    
    # Start with users not followed by current user
    suggestions = GupShupUser.objects.filter(
        is_active=True
    ).exclude(
        pk=current_user.pk
    ).exclude(
        pk__in=following_ids
    )
    
    # Prioritize users from same city/state
    if current_user.city or current_user.state:
        local_users = suggestions.filter(
            Q(city__iexact=current_user.city) |
            Q(state=current_user.state)
        ).order_by('-date_joined')[:limit//2]
        
        # Get remaining from general pool
        remaining = limit - len(local_users)
        if remaining > 0:
            other_users = suggestions.exclude(
                pk__in=[u.pk for u in local_users]
            ).order_by('-date_joined')[:remaining]
            
            suggestions = list(local_users) + list(other_users)
        else:
            suggestions = list(local_users)
    else:
        suggestions = list(suggestions.order_by('-date_joined')[:limit])
    
    return suggestions


def get_mutual_friends(user1, user2, limit=10):
    """
    Get mutual friends between two users
    """
    user1_following = Follow.objects.filter(
        follower=user1, status='accepted'
    ).values_list('following_id', flat=True)
    
    user2_following = Follow.objects.filter(
        follower=user2, status='accepted'
    ).values_list('following_id', flat=True)
    
    # Find intersection
    mutual_ids = set(user1_following).intersection(set(user2_following))
    
    if mutual_ids:
        return GupShupUser.objects.filter(
            pk__in=mutual_ids, is_active=True
        )[:limit]
    
    return []
