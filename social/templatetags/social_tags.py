from django import template
from django.contrib.auth.models import User

register = template.Library()

@register.filter
def get_mutual_friends_count(user1, user2):
    """
    Get the count of mutual friends between two users
    """
    if not user1 or not user2 or user1 == user2:
        return 0
    
    # Get users that user1 is following
    user1_following = set(user1.following.all().values_list('id', flat=True))
    # Get users that user2 is following  
    user2_following = set(user2.following.all().values_list('id', flat=True))
    
    # Find mutual friends (people both users are following)
    mutual_friends = user1_following.intersection(user2_following)
    
    return len(mutual_friends)

@register.filter
def get_mutual_friends(user1, user2, limit=5):
    """
    Get a list of mutual friends between two users
    """
    if not user1 or not user2 or user1 == user2:
        return []
    
    # Get users that user1 is following
    user1_following = user1.following.all()
    # Get users that user2 is following
    user2_following = user2.following.all()
    
    # Find mutual friends
    mutual_friends = user1_following.filter(id__in=user2_following.values_list('id', flat=True))[:limit]
    
    return mutual_friends