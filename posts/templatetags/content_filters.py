from django import template
import re

register = template.Library()

@register.filter
def remove_hashtags(content):
    """Remove hashtags from content to avoid duplication"""
    if not content:
        return content
    
    # Remove hashtags (words starting with #)
    hashtag_pattern = r'#\w+'
    clean_content = re.sub(hashtag_pattern, '', content)
    
    # Clean up extra spaces
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    
    return clean_content

@register.filter
def extract_hashtags(content):
    """Extract hashtags from content"""
    if not content:
        return []
    
    hashtag_pattern = r'#(\w+)'
    hashtags = re.findall(hashtag_pattern, content)
    return hashtags