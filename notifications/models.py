"""
Models for GupShup Notification System
Handles various types of notifications for user activities
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
import uuid


class Notification(models.Model):
    """
    Model to represent notifications for users
    """
    NOTIFICATION_TYPES = [
        ('follow', 'New Follower'),
        ('follow_request', 'Follow Request'),
        ('follow_accepted', 'Follow Request Accepted'),
        ('like', 'Post Liked'),
        ('comment', 'New Comment'),
        ('comment_reply', 'Comment Reply'),
        ('message', 'New Message'),
        ('mention', 'Mentioned in Post'),
        ('post_shared', 'Post Shared'),
        ('system', 'System Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Target user (who receives the notification)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Actor (who triggered the notification) - can be null for system notifications
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='triggered_notifications',
        null=True,
        blank=True
    )
    
    # Notification details
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    
    # Optional link for action
    action_url = models.CharField(max_length=500, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)  # For push notifications
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Related object IDs (for polymorphic references)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    object_type = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
    
    def mark_as_read(self):
        """
        Mark notification as read
        """
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def get_actor_name(self):
        """
        Get the display name of the actor
        """
        if self.actor:
            return self.actor.get_display_name()
        return "System"
    
    def get_time_since(self):
        """
        Get human-readable time since notification was created
        """
        from django.utils.timesince import timesince
        return timesince(self.created_at)
    
    def get_icon(self):
        """
        Get appropriate icon for notification type
        """
        icons = {
            'follow': 'bi-person-plus',
            'follow_request': 'bi-person-plus-fill',
            'follow_accepted': 'bi-person-check',
            'like': 'bi-heart-fill',
            'comment': 'bi-chat-fill',
            'comment_reply': 'bi-reply-fill',
            'message': 'bi-envelope-fill',
            'mention': 'bi-at',
            'post_shared': 'bi-share-fill',
            'system': 'bi-gear-fill',
        }
        return icons.get(self.notification_type, 'bi-bell-fill')
    
    def get_color_class(self):
        """
        Get appropriate color class for notification type
        """
        colors = {
            'follow': 'text-primary',
            'follow_request': 'text-info',
            'follow_accepted': 'text-success',
            'like': 'text-danger',
            'comment': 'text-primary',
            'comment_reply': 'text-primary',
            'message': 'text-warning',
            'mention': 'text-info',
            'post_shared': 'text-success',
            'system': 'text-secondary',
        }
        return colors.get(self.notification_type, 'text-primary')
    
    @classmethod
    def create_follow_notification(cls, follower, followed_user):
        """
        Create a notification when someone follows a user
        """
        return cls.objects.create(
            recipient=followed_user,
            actor=follower,
            notification_type='follow',
            title=f'{follower.get_display_name()} started following you',
            message=f'{follower.get_display_name()} (@{follower.username}) is now following you on GupShup!',
            action_url=f'/social/u/{follower.username}/'
        )
    
    @classmethod
    def create_like_notification(cls, liker, post):
        """
        Create a notification when someone likes a post
        """
        if liker == post.author:
            return None  # Don't notify users about their own likes
        
        return cls.objects.create(
            recipient=post.author,
            actor=liker,
            notification_type='like',
            title=f'{liker.get_display_name()} liked your post',
            message=f'{liker.get_display_name()} liked your post on GupShup.',
            action_url=f'/posts/{post.id}/',
            object_id=str(post.id),
            object_type='post'
        )
    
    @classmethod
    def create_comment_notification(cls, commenter, post, comment):
        """
        Create a notification when someone comments on a post
        """
        if commenter == post.author:
            return None  # Don't notify users about their own comments
        
        return cls.objects.create(
            recipient=post.author,
            actor=commenter,
            notification_type='comment',
            title=f'{commenter.get_display_name()} commented on your post',
            message=f'{commenter.get_display_name()} commented: "{comment.content[:50]}..."',
            action_url=f'/posts/{post.id}/',
            object_id=str(comment.id),
            object_type='comment'
        )
    
    @classmethod
    def create_message_notification(cls, sender, recipient, conversation):
        """
        Create a notification for new messages
        """
        return cls.objects.create(
            recipient=recipient,
            actor=sender,
            notification_type='message',
            title=f'New message from {sender.get_display_name()}',
            message=f'You have a new message from {sender.get_display_name()} on GupShup.',
            action_url=f'/messaging/{conversation.id}/',
            object_id=str(conversation.id),
            object_type='conversation'
        )


class NotificationSetting(models.Model):
    """
    Model to manage user notification preferences
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_settings'
    )
    
    # Email notification preferences
    email_on_follow = models.BooleanField(default=True)
    email_on_like = models.BooleanField(default=False)
    email_on_comment = models.BooleanField(default=True)
    email_on_message = models.BooleanField(default=True)
    email_on_mention = models.BooleanField(default=True)
    
    # Web notification preferences
    web_on_follow = models.BooleanField(default=True)
    web_on_like = models.BooleanField(default=True)
    web_on_comment = models.BooleanField(default=True)
    web_on_message = models.BooleanField(default=True)
    web_on_mention = models.BooleanField(default=True)
    
    # Push notification preferences (for PWA)
    push_on_follow = models.BooleanField(default=False)
    push_on_like = models.BooleanField(default=False)
    push_on_comment = models.BooleanField(default=False)
    push_on_message = models.BooleanField(default=True)
    push_on_mention = models.BooleanField(default=True)
    
    # General settings
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('never', 'Never'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ],
        default='daily'
    )
    
    quiet_hours_start = models.TimeField(null=True, blank=True, help_text="No notifications after this time")
    quiet_hours_end = models.TimeField(null=True, blank=True, help_text="No notifications before this time")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications_notificationsetting'
    
    def __str__(self):
        return f"Notification settings for {self.user.username}"
    
    def should_send_notification(self, notification_type, medium='web'):
        """
        Check if a notification should be sent based on user preferences
        """
        preference_map = {
            'web': {
                'follow': self.web_on_follow,
                'like': self.web_on_like,
                'comment': self.web_on_comment,
                'message': self.web_on_message,
                'mention': self.web_on_mention,
            },
            'email': {
                'follow': self.email_on_follow,
                'like': self.email_on_like,
                'comment': self.email_on_comment,
                'message': self.email_on_message,
                'mention': self.email_on_mention,
            },
            'push': {
                'follow': self.push_on_follow,
                'like': self.push_on_like,
                'comment': self.push_on_comment,
                'message': self.push_on_message,
                'mention': self.push_on_mention,
            },
        }
        
        return preference_map.get(medium, {}).get(notification_type, False)


# Signal handlers for automatic notification creation
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_notification_settings(sender, instance, created, **kwargs):
    """
    Create notification settings for new users
    """
    if created:
        NotificationSetting.objects.create(user=instance)
