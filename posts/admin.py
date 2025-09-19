from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Post, PostMedia


class PostMediaInline(admin.TabularInline):
    """
    Inline admin for post media files
    """
    model = PostMedia
    extra = 0
    fields = ('media_type', 'file', 'caption', 'order')


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """
    Admin interface for Posts with media management
    """
    
    list_display = [
        'get_content_preview', 'author', 'privacy', 'location',
        'likes_count', 'comments_count', 'views_count',
        'created_at', 'is_pinned'
    ]
    
    list_filter = [
        'privacy', 'is_pinned', 'is_edited', 'created_at',
        'author__state', 'author__city'
    ]
    
    search_fields = [
        'content', 'author__username', 'location', 'hashtags'
    ]
    
    readonly_fields = [
        'likes_count', 'comments_count', 'shares_count',
        'views_count', 'hashtags', 'created_at', 'updated_at'
    ]
    
    fieldsets = [
        (_('Content'), {
            'fields': ('author', 'content', 'privacy')
        }),
        (_('Location & Tags'), {
            'fields': ('location', 'hashtags'),
            'classes': ('collapse',)
        }),
        (_('Engagement'), {
            'fields': (
                'likes_count', 'comments_count',
                'shares_count', 'views_count'
            ),
            'classes': ('collapse',)
        }),
        (_('Settings'), {
            'fields': ('is_pinned', 'is_edited'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    ]
    
    inlines = [PostMediaInline]
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def get_content_preview(self, obj):
        """Return truncated content for list display"""
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    get_content_preview.short_description = _('Content Preview')


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    """
    Admin interface for Post Media
    """
    
    list_display = [
        'post', 'media_type', 'get_filename', 'caption', 'order', 'created_at'
    ]
    
    list_filter = ['media_type', 'created_at']
    
    search_fields = [
        'post__content', 'post__author__username', 'caption'
    ]
    
    ordering = ['post', 'order']
    
    def get_filename(self, obj):
        """Extract filename from file path"""
        return obj.file.name.split('/')[-1] if obj.file else 'No file'
    get_filename.short_description = _('File Name')
