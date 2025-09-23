from django import template
from django.utils.html import format_html
from django.templatetags.static import static
import re

register = template.Library()

@register.simple_tag
def get_video_thumbnail(post, media=None):
    """
    Get the appropriate video thumbnail based on post content and media filename
    Returns the path to the appropriate SVG thumbnail
    """
    
    # Get content and filename for analysis
    content = post.content.lower() if post.content else ""
    filename = ""
    
    if media and media.file:
        filename = media.file.name.lower()
    
    # Combined text for analysis
    combined_text = f"{content} {filename}"
    
    # Nature/Wildlife keywords
    nature_keywords = [
        'nature', 'forest', 'tree', 'bird', 'wildlife', 'animal', 'safari',
        'rain', 'monsoon', 'spring', 'moon', 'full moon', 'robin',
        'mountain', 'river', 'wildlife', 'green', 'natural'
    ]
    
    # City/Urban keywords
    city_keywords = [
        'city', 'urban', 'drone', 'building', 'metro', 'traffic',
        'street', 'downtown', 'skyline', 'architecture'
    ]
    
    # Music/Cultural keywords
    music_keywords = [
        'music', 'devotional', 'anthem', 'song', 'melody', 'cultural',
        'folk', 'classical', 'spiritual', 'jan gana mana', 'national anthem'
    ]
    
    # India/Patriotic keywords
    india_keywords = [
        'india', 'indian', 'unity', 'diversity', 'incredible', 'welcome',
        'national', 'flag', 'patriotic', 'bharat', 'hindustan'
    ]
    
    # Check keywords in combined text
    if any(keyword in combined_text for keyword in nature_keywords):
        return static('img/video-thumbnails/nature-video.svg')
    elif any(keyword in combined_text for keyword in city_keywords):
        return static('img/video-thumbnails/city-video.svg')
    elif any(keyword in combined_text for keyword in music_keywords):
        return static('img/video-thumbnails/music-video.svg')
    elif any(keyword in combined_text for keyword in india_keywords):
        return static('img/video-thumbnails/music-video.svg')  # Use music for Indian content
    else:
        return static('img/video-thumbnails/video-placeholder.svg')


@register.simple_tag
def get_video_description(post, media=None):
    """
    Get a descriptive text for the video thumbnail
    """
    
    content = post.content.lower() if post.content else ""
    filename = media.file.name.lower() if media and media.file else ""
    combined_text = f"{content} {filename}"
    
    if 'nature' in combined_text or 'forest' in combined_text or 'rain' in combined_text:
        return "🌿 NATURE VIDEO"
    elif 'city' in combined_text or 'drone' in combined_text or 'urban' in combined_text:
        return "🏙️ CITY VIDEO"
    elif 'music' in combined_text or 'devotional' in combined_text or 'anthem' in combined_text:
        return "🎵 MUSIC VIDEO"
    elif 'india' in combined_text or 'unity' in combined_text:
        return "🇮🇳 INDIA VIDEO"
    elif 'wildlife' in combined_text or 'animal' in combined_text or 'safari' in combined_text:
        return "🦁 WILDLIFE VIDEO"
    else:
        return "📹 VIDEO CONTENT"


@register.simple_tag
def render_video_thumbnail(post, media):
    """
    Render the complete video thumbnail HTML with smart detection
    """
    thumbnail_url = get_video_thumbnail(post, media)
    description = get_video_description(post, media)
    
    html = f'''
    <div class="position-relative video-container" style="border-radius: 10px; overflow: hidden; cursor: pointer;">
        <!-- Video thumbnail/poster -->
        <div class="video-thumbnail" style="position: relative; width: 100%; height: 225px; background: linear-gradient(135deg, #667eea, #764ba2); display: flex; align-items: center; justify-content: center;">
            <img src="{thumbnail_url}" alt="{description}" style="width: 100%; height: 100%; object-fit: cover;">
            
            <!-- Play overlay -->
            <div class="position-absolute top-50 start-50 translate-middle play-overlay" style="pointer-events: none;">
                <div class="bg-white rounded-circle d-flex align-items-center justify-content-center" style="width: 60px; height: 60px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                    <i class="bi bi-play-fill" style="font-size: 24px; color: #667eea; margin-left: 3px;"></i>
                </div>
            </div>
        </div>
        
        <!-- Hidden video element -->
        <video class="d-none video-element" 
               controls 
               style="width: 100%; max-height: 400px; object-fit: contain;"
               preload="metadata">
            <source src="{media.file.url}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
        
        <!-- Video badge -->
        <div class="position-absolute top-0 end-0 m-2">
            <div class="bg-dark bg-opacity-75 text-white rounded px-2 py-1 small">
                <i class="bi bi-play-circle"></i> Video
            </div>
        </div>
    </div>
    '''
    
    return format_html(html)