from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from posts.models import Post
import uuid


class Follow(models.Model):
    """
    Follow relationship between users
    Handles both following and friend requests
    """
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('accepted', _('Following')),
        ('blocked', _('Blocked')),
    ]
    
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='following',
        help_text=_('User who is following')
    )
    
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followers',
        help_text=_('User being followed')
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='accepted',
        help_text=_('Follow request status')
    )
    
    # Mutual following indicates friendship
    is_mutual = models.BooleanField(
        default=False,
        help_text=_('Both users follow each other')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        db_table = 'gupshup_follows'
        verbose_name = _('Follow')
        verbose_name_plural = _('Follows')
        unique_together = ['follower', 'following']
        indexes = [
            models.Index(fields=['follower', 'status']),
            models.Index(fields=['following', 'status']),
            models.Index(fields=['is_mutual']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        status_emoji = {
            'pending': '⏳',
            'accepted': '✓',
            'blocked': '❌'
        }
        return f"@{self.follower.username} → @{self.following.username} {status_emoji.get(self.status, '')}"
    
    def clean(self):
        """Prevent self-following"""
        from django.core.exceptions import ValidationError
        if self.follower == self.following:
            raise ValidationError(_('Users cannot follow themselves'))
    
    def save(self, *args, **kwargs):
        """Update mutual following status"""
        super().save(*args, **kwargs)
        
        # Check if this creates a mutual follow
        if self.status == 'accepted':
            mutual_follow = Follow.objects.filter(
                follower=self.following,
                following=self.follower,
                status='accepted'
            ).first()
            
            if mutual_follow:
                # Update both relationships as mutual
                Follow.objects.filter(
                    models.Q(follower=self.follower, following=self.following) |
                    models.Q(follower=self.following, following=self.follower)
                ).update(is_mutual=True)


class Like(models.Model):
    """
    Like model for posts
    Optimized for quick like/unlike operations
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes',
        help_text=_('User who liked')
    )
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='likes',
        help_text=_('Liked post')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        db_table = 'gupshup_likes'
        verbose_name = _('Like')
        verbose_name_plural = _('Likes')
        unique_together = ['user', 'post']
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"@{self.user.username} liked @{self.post.author.username}'s post"
    
    def save(self, *args, **kwargs):
        """Update post like count"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Increment like count
            Post.objects.filter(pk=self.post.pk).update(
                likes_count=models.F('likes_count') + 1
            )
    
    def delete(self, *args, **kwargs):
        """Update post like count on delete"""
        post_pk = self.post.pk
        super().delete(*args, **kwargs)
        
        # Decrement like count
        Post.objects.filter(pk=post_pk).update(
            likes_count=models.F('likes_count') - 1
        )


class Comment(models.Model):
    """
    Comment model for posts
    Supports nested comments (replies)
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text=_('Post being commented on')
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text=_('Comment author')
    )
    
    content = models.TextField(
        max_length=500,
        help_text=_('Comment text (supports Hindi and English)')
    )
    
    # For nested comments (replies)
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='replies',
        help_text=_('Parent comment if this is a reply')
    )
    
    # Engagement
    likes_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of likes on comment')
    )
    
    replies_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of replies')
    )
    
    # Flags
    is_edited = models.BooleanField(
        default=False,
        help_text=_('Comment has been edited')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        db_table = 'gupshup_comments'
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['parent_comment']),
        ]
    
    def __str__(self):
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"@{self.author.username}: {content_preview}"
    
    def save(self, *args, **kwargs):
        """Update post comment count and parent reply count"""
        is_new = self.pk is None
        
        # Set is_edited if this is an update
        if not is_new and 'update_fields' not in kwargs:
            self.is_edited = True
        
        super().save(*args, **kwargs)
        
        if is_new:
            # Increment post comment count
            Post.objects.filter(pk=self.post.pk).update(
                comments_count=models.F('comments_count') + 1
            )
            
            # Increment parent comment reply count
            if self.parent_comment:
                Comment.objects.filter(pk=self.parent_comment.pk).update(
                    replies_count=models.F('replies_count') + 1
                )
    
    def delete(self, *args, **kwargs):
        """Update counts on delete"""
        post_pk = self.post.pk
        parent_comment_pk = self.parent_comment.pk if self.parent_comment else None
        
        super().delete(*args, **kwargs)
        
        # Decrement post comment count
        Post.objects.filter(pk=post_pk).update(
            comments_count=models.F('comments_count') - 1
        )
        
        # Decrement parent comment reply count
        if parent_comment_pk:
            Comment.objects.filter(pk=parent_comment_pk).update(
                replies_count=models.F('replies_count') - 1
            )
    
    def get_absolute_url(self):
        """Return URL for this comment"""
        from django.urls import reverse
        return f"{self.post.get_absolute_url()}#comment-{self.pk}"


class CommentLike(models.Model):
    """
    Like model for comments
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comment_likes',
        help_text=_('User who liked comment')
    )
    
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='likes',
        help_text=_('Liked comment')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        db_table = 'gupshup_comment_likes'
        verbose_name = _('Comment Like')
        verbose_name_plural = _('Comment Likes')
        unique_together = ['user', 'comment']
        indexes = [
            models.Index(fields=['comment', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"@{self.user.username} liked @{self.comment.author.username}'s comment"
    
    def save(self, *args, **kwargs):
        """Update comment like count"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            Comment.objects.filter(pk=self.comment.pk).update(
                likes_count=models.F('likes_count') + 1
            )
    
    def delete(self, *args, **kwargs):
        """Update comment like count on delete"""
        comment_pk = self.comment.pk
        super().delete(*args, **kwargs)
        
        Comment.objects.filter(pk=comment_pk).update(
            likes_count=models.F('likes_count') - 1
        )
