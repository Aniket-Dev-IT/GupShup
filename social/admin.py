from django.contrib import admin
from .models import Follow, Like, Comment

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['follower__username', 'following__username']
    list_select_related = ['follower', 'following']
    date_hierarchy = 'created_at'
    
@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'post__content']
    list_select_related = ['user', 'post']
    date_hierarchy = 'created_at'
    
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'post', 'content_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['author__username', 'post__content', 'content']
    list_select_related = ['author', 'post']
    date_hierarchy = 'created_at'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'
