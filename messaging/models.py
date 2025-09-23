"""
Models for GupShup Messaging System
Handles one-on-one conversations and messages between users
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
import uuid


class Conversation(models.Model):
    """
    Model to represent a conversation between two users
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Participants in the conversation
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_initiated'
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_received'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Last message timestamp for ordering
    last_message_at = models.DateTimeField(null=True, blank=True)
    
    # Privacy and status
    is_active = models.BooleanField(default=True)
    
    # Blocked status (if either user blocks the other)
    is_blocked = models.BooleanField(default=False)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_conversations',
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-last_message_at', '-updated_at']
        unique_together = ['user1', 'user2']
        indexes = [
            models.Index(fields=['-last_message_at']),
            models.Index(fields=['user1', 'user2']),
        ]
    
    def __str__(self):
        return f"Conversation between {self.user1.username} and {self.user2.username}"
    
    def get_absolute_url(self):
        return reverse('messaging:conversation_detail', kwargs={'conversation_id': self.id})
    
    def get_other_user(self, user):
        """
        Get the other participant in the conversation
        """
        if user == self.user1:
            return self.user2
        return self.user1
    
    def is_participant(self, user):
        """
        Check if the user is a participant in this conversation
        """
        return user == self.user1 or user == self.user2
    
    def get_last_message(self):
        """
        Get the last message in this conversation
        """
        return self.messages.filter(is_deleted=False).first()
    
    def get_unread_count(self, user):
        """
        Get the number of unread messages for a user
        """
        return self.messages.filter(
            is_deleted=False,
            is_read=False
        ).exclude(sender=user).count()
    
    def mark_messages_read(self, user):
        """
        Mark all messages as read for a specific user
        """
        self.messages.filter(
            is_deleted=False,
            is_read=False
        ).exclude(sender=user).update(is_read=True)
    
    @classmethod
    def get_or_create_conversation(cls, user1, user2):
        """
        Get existing conversation or create a new one between two users
        """
        # Ensure consistent ordering to prevent duplicate conversations
        if user1.id > user2.id:
            user1, user2 = user2, user1
        
        conversation, created = cls.objects.get_or_create(
            user1=user1,
            user2=user2,
            defaults={'is_active': True}
        )
        
        return conversation, created
    
    @classmethod
    def get_user_conversations(cls, user):
        """
        Get all conversations for a user, ordered by latest activity
        """
        return cls.objects.filter(
            models.Q(user1=user) | models.Q(user2=user),
            is_active=True
        ).select_related('user1', 'user2').prefetch_related('messages')


class Message(models.Model):
    """
    Model to represent individual messages within conversations
    """
    MESSAGE_TYPES = [
        ('text', 'Text Message'),
        ('image', 'Image Message'),
        ('file', 'File Message'),
        ('system', 'System Message'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationship to conversation and sender
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(blank=True)  # Text content
    
    # File attachments (if any)
    image = models.ImageField(upload_to='messages/images/', null=True, blank=True)
    file = models.FileField(upload_to='messages/files/', null=True, blank=True)
    
    # Status fields
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    
    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    # Reply functionality (optional)
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['conversation', '-sent_at']),
            models.Index(fields=['sender', '-sent_at']),
            models.Index(fields=['is_read', 'is_deleted']),
        ]
    
    def __str__(self):
        if self.message_type == 'text':
            return f"{self.sender.username}: {self.content[:50]}..."
        else:
            return f"{self.sender.username}: [{self.message_type.upper()}]"
    
    def save(self, *args, **kwargs):
        """
        Override save to update conversation's last_message_at
        """
        super().save(*args, **kwargs)
        
        # Update conversation's last message timestamp
        if not self.is_deleted:
            self.conversation.last_message_at = self.sent_at
            self.conversation.save(update_fields=['last_message_at'])
    
    def mark_as_read(self):
        """
        Mark this message as read
        """
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def can_delete(self, user):
        """
        Check if user can delete this message
        """
        # Only sender can delete their own messages and only if not already deleted
        return self.sender == user and not self.is_deleted
    
    def soft_delete(self):
        """
        Soft delete the message
        """
        self.is_deleted = True
        self.save(update_fields=['is_deleted'])
    
    def get_image_url(self):
        """
        Get image URL if message has image
        """
        if self.image:
            return self.image.url
        return None
    
    def get_file_name(self):
        """
        Get the original file name for file messages
        """
        if self.file:
            return self.file.name.split('/')[-1]
        return None
    
    def is_sender(self, user):
        """
        Check if the user is the sender of this message
        """
        return self.sender == user
    
    def can_edit(self, user):
        """
        Check if the user can edit this message
        """
        # Only sender can edit, and only text messages within 5 minutes
        if self.sender != user or self.message_type != 'text':
            return False
        
        time_limit = timezone.now() - timezone.timedelta(minutes=5)
        return self.sent_at > time_limit and not self.is_edited
    


# Signal to update conversation timestamp when a message is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Message)
def update_conversation_timestamp(sender, instance, created, **kwargs):
    """
    Update conversation's last_message_at when a new message is created
    """
    if created and not instance.is_deleted:
        conversation = instance.conversation
        conversation.last_message_at = instance.sent_at
        conversation.save(update_fields=['last_message_at', 'updated_at'])
