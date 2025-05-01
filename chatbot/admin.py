from django.contrib import admin
from .models import ChatbotConversation, ChatMessage, ConversationSummary


@admin.register(ChatbotConversation)
class ChatbotConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "created_at", "last_activity", "is_active")
    list_filter = ("is_active", "created_at", "last_activity")
    search_fields = ("title", "user__username", "user__email")
    readonly_fields = ("created_at", "last_activity")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "is_bot",
        "message_type",
        "timestamp",
    )
    list_filter = ("is_bot", "message_type", "timestamp")
    search_fields = ("content", "sender__username", "conversation__id")
    readonly_fields = ("timestamp",)


@admin.register(ConversationSummary)
class ConversationSummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "created_at", "message_count")
    list_filter = ("created_at",)
    search_fields = ("summary_text", "conversation__id")
    readonly_fields = ("created_at",)
