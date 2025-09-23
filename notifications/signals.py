from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from social.models import Like, Comment, Follow
from messaging.models import Message
from .models import Notification

User = get_user_model()


@receiver(post_save, sender=Like)
def create_like_notification(sender, instance, created, **kwargs):
    """Create notification when someone likes a post"""
    if created and instance.post.author != instance.user:
        # Don't create notification if user likes their own post
        Notification.objects.create(
            recipient=instance.post.author,
            actor=instance.user,
            notification_type='like',
            title=f"{instance.user.get_display_name()} liked your post",
            message=f"{instance.user.get_display_name()} liked your post: \"{instance.post.content[:50]}{'...' if len(instance.post.content) > 50 else ''}\""
        )


@receiver(post_delete, sender=Like)
def delete_like_notification(sender, instance, **kwargs):
    """Delete notification when like is removed"""
    Notification.objects.filter(
        recipient=instance.post.author,
        actor=instance.user,
        notification_type='like'
    ).delete()


@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    """Create notification when someone comments on a post"""
    if created and instance.post.author != instance.author:
        # Don't create notification if user comments on their own post
        Notification.objects.create(
            recipient=instance.post.author,
            actor=instance.author,
            notification_type='comment',
            title=f"{instance.author.get_display_name()} commented on your post",
            message=f"{instance.author.get_display_name()} commented on your post: \"{instance.content[:50]}{'...' if len(instance.content) > 50 else ''}\""
        )
        
        # Also notify mentioned users (if any)
        content = instance.content
        words = content.split()
        for word in words:
            if word.startswith('@') and len(word) > 1:
                username = word[1:].strip('.,!?;:')
                try:
                    mentioned_user = User.objects.get(username=username)
                    if mentioned_user != instance.author and mentioned_user != instance.post.author:
                        Notification.objects.create(
                            recipient=mentioned_user,
                            actor=instance.author,
                            notification_type='mention',
                            title=f"{instance.author.get_display_name()} mentioned you",
                            message=f"{instance.author.get_display_name()} mentioned you in a comment: \"{instance.content[:50]}{'...' if len(instance.content) > 50 else ''}\""
                        )
                except User.DoesNotExist:
                    pass


@receiver(post_delete, sender=Comment)
def delete_comment_notification(sender, instance, **kwargs):
    """Delete notification when comment is removed"""
    Notification.objects.filter(
        recipient=instance.post.author,
        actor=instance.author,
        notification_type='comment'
    ).delete()


@receiver(post_save, sender=Follow)
def create_follow_notification(sender, instance, created, **kwargs):
    """Create notification when someone follows a user"""
    if created:
        Notification.objects.create(
            recipient=instance.following,
            actor=instance.follower,
            notification_type='follow',
            title=f"{instance.follower.get_display_name()} started following you",
            message=f"{instance.follower.get_display_name()} started following you"
        )


@receiver(post_delete, sender=Follow)
def delete_follow_notification(sender, instance, **kwargs):
    """Delete notification when follow is removed"""
    Notification.objects.filter(
        recipient=instance.following,
        actor=instance.follower,
        notification_type='follow'
    ).delete()


@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    """Create notification when someone sends a message"""
    if created:
        recipient = instance.conversation.participants.exclude(id=instance.sender.id).first()
        if recipient:
            Notification.objects.create(
                recipient=recipient,
                actor=instance.sender,
                notification_type='message',
                title=f"New message from {instance.sender.get_display_name()}",
                message=f"{instance.sender.get_display_name()} sent you a message: \"{instance.content[:50]}{'...' if len(instance.content) > 50 else ''}\""
            )
