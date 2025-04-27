from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html
from feeds.models import (
    Post, 
    Comment, 
    Topic, 
    Reaction, 
    SavedPost, 
    HiddenPost, 
    PollOption, 
    PollVote
)


class PollOptionInline(admin.TabularInline):
    """Inline editor for poll options"""
    model = PollOption
    extra = 1
    readonly_fields = ['created_at']


class CommentInline(admin.TabularInline):
    """Inline editor for comments"""
    model = Comment
    extra = 0
    readonly_fields = ['author', 'created_at', 'updated_at', 'is_edited']
    fields = ['content', 'author', 'created_at', 'is_edited']
    show_change_link = True
    max_num = 5
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    """Admin interface for Topics"""
    list_display = ['name', 'description', 'color_display', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def color_display(self, obj):
        """Display color as a colored square"""
        if obj.color:
            return format_html(
                '<div style="background-color:{}; width:20px; height:20px; border-radius:3px;"></div>',
                obj.color
            )
        return '-'
    color_display.short_description = 'Color'


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """Admin interface for Posts"""
    list_display = [
        'id', 'short_content', 'author', 'post_type', 
        'visibility', 'created_at', 'views_count', 'is_featured'
    ]
    list_filter = [
        'post_type', 'visibility', 'is_featured', 'is_pinned',
        'is_archived', 'created_at', 'topics'
    ]
    search_fields = ['content', 'author__username', 'tags']
    readonly_fields = ['created_at', 'updated_at', 'views_count']
    filter_horizontal = ['topics', 'media_files']
    inlines = [PollOptionInline, CommentInline]
    date_hierarchy = 'created_at'
    
    fieldsets = [
        ('Content', {
            'fields': ['author', 'content', 'post_type', 'tags']
        }),
        ('Settings', {
            'fields': ['topics', 'visibility', 'is_pinned', 'is_featured', 'is_archived']
        }),
        ('Media', {
            'fields': ['media_files']
        }),
        ('Link Details', {
            'fields': ['link_url', 'link_title', 'link_description', 'link_image'],
            'classes': ['collapse']
        }),
        ('Statistics', {
            'fields': ['views_count', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def short_content(self, obj):
        """Display truncated content"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    short_content.short_description = 'Content'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin interface for Comments"""
    list_display = ['id', 'short_content', 'author', 'post', 'created_at', 'is_edited', 'has_parent']
    list_filter = ['created_at', 'is_edited', 'author']
    search_fields = ['content', 'author__username', 'post__content']
    readonly_fields = ['created_at', 'updated_at']
    
    def short_content(self, obj):
        """Display truncated content"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    short_content.short_description = 'Content'
    
    def has_parent(self, obj):
        """Check if comment is a reply"""
        return obj.parent is not None
    has_parent.boolean = True
    has_parent.short_description = 'Is Reply'


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    """Admin interface for Reactions"""
    list_display = ['id', 'user', 'reaction_type', 'content_type', 'object_id', 'created_at']
    list_filter = ['reaction_type', 'created_at', 'content_type']
    search_fields = ['user__username', 'reaction_type']
    readonly_fields = ['created_at']


@admin.register(SavedPost)
class SavedPostAdmin(admin.ModelAdmin):
    """Admin interface for SavedPosts"""
    list_display = ['id', 'user', 'post', 'saved_at']
    list_filter = ['saved_at']
    search_fields = ['user__username', 'post__content']
    readonly_fields = ['saved_at']


@admin.register(HiddenPost)
class HiddenPostAdmin(admin.ModelAdmin):
    """Admin interface for HiddenPosts"""
    list_display = ['id', 'user', 'post', 'hidden_at', 'reason']
    list_filter = ['hidden_at']
    search_fields = ['user__username', 'post__content', 'reason']
    readonly_fields = ['hidden_at']


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    """Admin interface for PollOptions"""
    list_display = ['id', 'option_text', 'post', 'created_at', 'votes_count']
    list_filter = ['created_at']
    search_fields = ['option_text', 'post__content']
    readonly_fields = ['created_at']
    
    def votes_count(self, obj):
        """Get the number of votes for this option"""
        return obj.votes.count()
    votes_count.short_description = 'Votes'


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    """Admin interface for PollVotes"""
    list_display = ['id', 'user', 'poll_option', 'voted_at']
    list_filter = ['voted_at']
    search_fields = ['user__username', 'poll_option__option_text']
    readonly_fields = ['voted_at']
