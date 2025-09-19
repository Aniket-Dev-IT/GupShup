from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch, F
from django.db import models
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
import json
import re
from collections import Counter

from .models import Post, PostMedia
from .forms import PostCreationForm, CommentForm, PostEditForm, HashtagSearchForm, PostSearchForm
from social.models import Like, Comment, Follow
from accounts.models import GupShupUser


@login_required
def feed_view(request):
    """
    Main feed view showing posts from followed users and trending content
    """
    user = request.user
    
    # Get users that current user is following
    following_users = Follow.objects.filter(
        follower=user, 
        status='accepted'
    ).values_list('following', flat=True)
    
    # Build feed query with optimized database access
    feed_posts = Post.objects.select_related('author').prefetch_related(
        'media_files',
        'likes',
        Prefetch('comments', queryset=Comment.objects.select_related('author').order_by('-created_at')[:3])
    )
    
    # Filter posts based on privacy and following
    if following_users.exists():
        # Show posts from followed users + own posts + public posts
        feed_posts = feed_posts.filter(
            Q(author__in=following_users) |
            Q(author=user) |
            Q(privacy='public')
        )
    else:
        # New user - show public posts + own posts
        feed_posts = feed_posts.filter(
            Q(author=user) |
            Q(privacy='public')
        )
    
    # Order by creation date (most recent first)
    feed_posts = feed_posts.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(feed_posts, 10)  # 10 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get trending hashtags (Indian context)
    trending_hashtags = get_trending_hashtags()
    
    # Check if user has liked each post
    for post in page_obj:
        post.user_has_liked = post.likes.filter(user=user).exists()
        post.recent_comments = post.comments.all()[:3]
    
    # Post creation form
    if request.method == 'POST':
        form = PostCreationForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            post = form.save()
            messages.success(request, f'Your post has been shared! 🎉')
            return redirect('posts:feed')
        else:
            messages.error(request, 'Please correct the errors in your post.')
    else:
        form = PostCreationForm(user=user)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'trending_hashtags': trending_hashtags,
        'user': user,
        'title': 'GupShup Feed'
    }
    
    return render(request, 'posts/feed.html', context)


@login_required
def create_post_view(request):
    """
    Standalone post creation view
    """
    if request.method == 'POST':
        form = PostCreationForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            post = form.save()
            messages.success(request, f'Post created successfully! 🎉')
            return redirect('posts:detail', pk=post.pk)
    else:
        form = PostCreationForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create New Post'
    }
    
    return render(request, 'posts/create_post.html', context)


def post_detail_view(request, pk):
    """
    Detailed view of a single post with comments
    """
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related(
            'media_files',
            'likes__user',
            'comments__author',
            'comments__likes__user'
        ),
        pk=pk
    )
    
    # Check privacy permissions
    if post.privacy == 'private' and post.author != request.user:
        raise Http404('Post not found')
    elif post.privacy == 'friends' and not request.user.is_authenticated:
        raise Http404('Post not found')
    elif post.privacy == 'friends' and request.user.is_authenticated:
        # Check if user is following the author
        if not Follow.objects.filter(
            follower=request.user, 
            following=post.author, 
            status='accepted'
        ).exists() and post.author != request.user:
            raise Http404('Post not found')
    
    # Increment view count
    Post.objects.filter(pk=pk).update(views_count=F('views_count') + 1)
    
    # Get comments with replies
    comments = post.comments.filter(parent_comment=None).order_by('-created_at')
    
    # Check user interactions
    user_has_liked = False
    if request.user.is_authenticated:
        user_has_liked = post.likes.filter(user=request.user).exists()
    
    # Comment form handling
    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = CommentForm(request.POST, user=request.user, post=post)
        if comment_form.is_valid():
            comment = comment_form.save()
            messages.success(request, 'Comment added! 💬')
            return redirect('posts:detail', pk=pk)
    else:
        comment_form = CommentForm() if request.user.is_authenticated else None
    
    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'user_has_liked': user_has_liked,
        'title': f'Post by @{post.author.username}'
    }
    
    return render(request, 'posts/post_detail.html', context)


@login_required
@require_POST
def like_post_view(request):
    """
    AJAX view to like/unlike posts
    """
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        post = get_object_or_404(Post, pk=post_id)
        
        # Check if user already liked the post
        like, created = Like.objects.get_or_create(
            user=request.user,
            post=post
        )
        
        if not created:
            # User already liked, so unlike
            like.delete()
            liked = False
        else:
            liked = True
        
        # Get updated like count
        like_count = post.likes.count()
        
        return JsonResponse({
            'success': True,
            'liked': liked,
            'like_count': like_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def edit_post_view(request, pk):
    """
    Edit existing post (only by author)
    """
    post = get_object_or_404(Post, pk=pk, author=request.user)
    
    if request.method == 'POST':
        form = PostEditForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'Post updated successfully! ✏️')
            return redirect('posts:detail', pk=pk)
    else:
        form = PostEditForm(instance=post)
    
    context = {
        'form': form,
        'post': post,
        'title': 'Edit Post'
    }
    
    return render(request, 'posts/edit_post.html', context)


@login_required
def delete_post_view(request, pk):
    """
    Delete post (only by author)
    """
    post = get_object_or_404(Post, pk=pk, author=request.user)
    
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Post deleted successfully! 🗑️')
        return redirect('posts:feed')
    
    context = {
        'post': post,
        'title': 'Delete Post'
    }
    
    return render(request, 'posts/delete_post.html', context)


def explore_view(request):
    """
    Explore page with trending posts, hashtags, and Indian content
    """
    # Get trending posts (most liked/commented in last 7 days)
    from datetime import datetime, timedelta
    
    week_ago = datetime.now() - timedelta(days=7)
    
    trending_posts = Post.objects.filter(
        privacy='public',
        created_at__gte=week_ago
    ).select_related('author').prefetch_related('media_files').annotate(
        engagement_score=Count('likes') + Count('comments')
    ).order_by('-engagement_score', '-created_at')[:20]
    
    # Get trending hashtags
    trending_hashtags = get_trending_hashtags()
    
    # Get posts from popular Indian cities
    indian_city_posts = Post.objects.filter(
        privacy='public',
        location__iregex=r'(mumbai|delhi|bangalore|chennai|kolkata|hyderabad|pune)'
    ).select_related('author').order_by('-created_at')[:10]
    
    context = {
        'trending_posts': trending_posts,
        'trending_hashtags': trending_hashtags,
        'indian_city_posts': indian_city_posts,
        'title': 'Explore GupShup'
    }
    
    return render(request, 'posts/explore.html', context)


def hashtag_posts_view(request, hashtag):
    """
    Show all posts with a specific hashtag
    """
    # Clean hashtag
    hashtag = hashtag.strip().lower()
    if hashtag.startswith('#'):
        hashtag = hashtag[1:]
    
    # Find posts with this hashtag
    posts = Post.objects.filter(
        privacy='public',
        hashtags__icontains=hashtag
    ).select_related('author').prefetch_related('media_files').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(posts, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get related hashtags
    related_hashtags = get_related_hashtags(hashtag)
    
    context = {
        'hashtag': hashtag,
        'page_obj': page_obj,
        'related_hashtags': related_hashtags,
        'title': f'#{hashtag} - GupShup'
    }
    
    return render(request, 'posts/hashtag_posts.html', context)


def search_posts_view(request):
    """
    Search posts with various filters
    """
    form = PostSearchForm(request.GET or None)
    posts = Post.objects.none()
    query = ''
    
    if form.is_valid():
        query = form.cleaned_data.get('query', '')
        search_type = form.cleaned_data.get('search_type', 'all')
        location = form.cleaned_data.get('location', '')
        
        # Start with public posts
        posts = Post.objects.filter(privacy='public')
        
        # Apply query filter
        if query:
            posts = posts.filter(
                Q(content__icontains=query) |
                Q(hashtags__icontains=query) |
                Q(location__icontains=query) |
                Q(author__username__icontains=query) |
                Q(author__first_name__icontains=query) |
                Q(author__last_name__icontains=query)
            )
        
        # Apply type filter
        if search_type == 'media':
            posts = posts.filter(media_files__isnull=False)
        elif search_type == 'location':
            posts = posts.exclude(location='')
        elif search_type == 'text':
            posts = posts.filter(media_files__isnull=True)
        
        # Apply location filter
        if location:
            posts = posts.filter(location__icontains=location)
        
        posts = posts.select_related('author').prefetch_related('media_files').distinct().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(posts, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'query': query,
        'title': f'Search: {query}' if query else 'Search Posts'
    }
    
    return render(request, 'posts/search_posts.html', context)


# Helper functions

def get_trending_hashtags(limit=10):
    """
    Get trending hashtags from recent posts
    """
    from datetime import datetime, timedelta
    
    # Get posts from last 3 days
    recent_date = datetime.now() - timedelta(days=3)
    recent_posts = Post.objects.filter(
        privacy='public',
        created_at__gte=recent_date,
        hashtags__isnull=False
    ).exclude(hashtags='')
    
    # Extract all hashtags
    all_hashtags = []
    for post in recent_posts:
        if post.hashtags:
            hashtags = [tag.strip() for tag in post.hashtags.split(',') if tag.strip()]
            all_hashtags.extend(hashtags)
    
    # Count hashtag frequency
    hashtag_counts = Counter(all_hashtags)
    
    # Add some popular Indian hashtags if list is small
    indian_hashtags = [
        'Mumbai', 'Delhi', 'Bangalore', 'India', 'Cricket', 'Bollywood',
        'Food', 'Travel', 'Festival', 'Culture', 'Technology', 'Startup'
    ]
    
    if len(hashtag_counts) < 5:
        for tag in indian_hashtags[:5]:
            if tag.lower() not in [h.lower() for h in hashtag_counts.keys()]:
                hashtag_counts[tag] = 1
    
    return [{'name': tag, 'count': count} for tag, count in hashtag_counts.most_common(limit)]


def get_related_hashtags(hashtag, limit=5):
    """
    Get hashtags that frequently appear with the given hashtag
    """
    # Find posts with this hashtag
    posts_with_hashtag = Post.objects.filter(
        privacy='public',
        hashtags__icontains=hashtag
    ).exclude(hashtags='')
    
    # Extract all other hashtags from these posts
    related_tags = []
    for post in posts_with_hashtag:
        if post.hashtags:
            tags = [tag.strip() for tag in post.hashtags.split(',') if tag.strip()]
            # Remove the current hashtag
            tags = [tag for tag in tags if tag.lower() != hashtag.lower()]
            related_tags.extend(tags)
    
    # Count and return most common
    tag_counts = Counter(related_tags)
    return [tag for tag, count in tag_counts.most_common(limit)]
