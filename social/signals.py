"""
Django signals for maintaining count fields in GupShup models
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import models

from .models import Follow
from accounts.models import GupShupUser


@receiver(post_save, sender=Follow)
def update_follow_counts_on_create(sender, instance, created, **kwargs):
    """
    Update follower and following counts when a Follow relationship is created
    Only count 'accepted' follows
    """
    if created and instance.status == 'accepted':
        # Increment following count for follower
        GupShupUser.objects.filter(pk=instance.follower.pk).update(
            following_count=models.F('following_count') + 1
        )
        
        # Increment followers count for following
        GupShupUser.objects.filter(pk=instance.following.pk).update(
            followers_count=models.F('followers_count') + 1
        )


@receiver(post_delete, sender=Follow)
def update_follow_counts_on_delete(sender, instance, **kwargs):
    """
    Update follower and following counts when a Follow relationship is deleted
    Only count 'accepted' follows
    """
    if instance.status == 'accepted':
        # Decrement following count for follower
        GupShupUser.objects.filter(pk=instance.follower.pk).update(
            following_count=models.F('following_count') - 1
        )
        
        # Decrement followers count for following
        GupShupUser.objects.filter(pk=instance.following.pk).update(
            followers_count=models.F('followers_count') - 1
        )


@receiver(post_save, sender=Follow)
def update_follow_counts_on_status_change(sender, instance, created, **kwargs):
    """
    Handle status changes from pending to accepted or vice versa
    """
    if not created:
        # This is an update, check if status changed
        # We need to get the old instance to compare
        try:
            old_instance = Follow.objects.get(pk=instance.pk)
            
            # If status changed from pending to accepted
            if old_instance.status != 'accepted' and instance.status == 'accepted':
                # Increment counts
                GupShupUser.objects.filter(pk=instance.follower.pk).update(
                    following_count=models.F('following_count') + 1
                )
                GupShupUser.objects.filter(pk=instance.following.pk).update(
                    followers_count=models.F('followers_count') + 1
                )
            
            # If status changed from accepted to pending/blocked
            elif old_instance.status == 'accepted' and instance.status != 'accepted':
                # Decrement counts
                GupShupUser.objects.filter(pk=instance.follower.pk).update(
                    following_count=models.F('following_count') - 1
                )
                GupShupUser.objects.filter(pk=instance.following.pk).update(
                    followers_count=models.F('followers_count') - 1
                )
        
        except Follow.DoesNotExist:
            # Handle edge case where instance doesn't exist
            pass


# Import and register Post signals
from posts.models import Post

@receiver(post_save, sender=Post)
def update_post_count_on_create(sender, instance, created, **kwargs):
    """
    Update user's post count when a new post is created
    """
    if created:
        GupShupUser.objects.filter(pk=instance.author.pk).update(
            posts_count=models.F('posts_count') + 1
        )


@receiver(post_delete, sender=Post)
def update_post_count_on_delete(sender, instance, **kwargs):
    """
    Update user's post count when a post is deleted
    """
    GupShupUser.objects.filter(pk=instance.author.pk).update(
        posts_count=models.F('posts_count') - 1
    )