from django.contrib import admin
from .models.one_to_one import OneToOneConversation, OneToOneMessage
from .models.group import GroupConversation, GroupMessage
from .models.chatbot import ChatbotConversation, ChatbotMessage


@admin.register(OneToOneConversation)
class OneToOneConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "get_participants", "created_at", "is_active")
    search_fields = ("participants__username",)
    list_filter = ("is_active", "created_at")

    def get_participants(self, obj):
        return ", ".join([user.username for user in obj.participants.all()])

    get_participants.short_description = "Participants"


@admin.register(OneToOneMessage)
class OneToOneMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "timestamp", "content_preview")
    search_fields = ("sender__username", "content")
    list_filter = ("timestamp",)

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Message Preview"


@admin.register(GroupConversation)
class GroupConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_private", "created_at")
    search_fields = ("name",)
    list_filter = ("is_private", "created_at")


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "timestamp",
        "message_type",
        "content_preview",
    )
    search_fields = ("sender__username", "content")
    list_filter = ("timestamp", "message_type")

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Message Preview"


@admin.register(ChatbotConversation)
class ChatbotConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    search_fields = ("user__username",)
    list_filter = ("created_at",)


@admin.register(ChatbotMessage)
class ChatbotMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "timestamp",
        "is_bot",
        "content_preview",
    )
    search_fields = ("sender__username", "content")
    list_filter = ("timestamp", "is_bot")

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Message Preview"
