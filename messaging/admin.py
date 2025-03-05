from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Conversation, Message, Reaction


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation_type",
        "group_name_display",
        "participants_count",
        "messages_count",
        "created_at",
        "is_active",
    )
    list_filter = ("conversation_type", "is_active", "created_at")
    search_fields = ("group_name", "participants__username")
    filter_horizontal = ("participants", "moderators")
    readonly_fields = ("created_at",)
    list_per_page = 20

    def group_name_display(self, obj):
        return obj.group_name if obj.group_name else f"Conversation #{obj.id}"

    group_name_display.short_description = "Name"

    def participants_count(self, obj):
        return obj.participants.count()

    participants_count.short_description = "Participants"

    def messages_count(self, obj):
        return obj.messages.count()

    messages_count.short_description = "Messages"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "formatted_content",
        "sender_link",
        "conversation_link",
        "message_type",
        "timestamp",
        "is_chatbot",
        "read_count",
    )
    list_filter = ("message_type", "is_chatbot", "timestamp", "content_type")
    search_fields = ("content", "sender__username", "conversation__group_name")
    raw_id_fields = ("sender", "conversation")
    readonly_fields = ("timestamp",)
    list_per_page = 50

    def formatted_content(self, obj):
        content = obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
        return format_html('<span title="{}">{}</span>', obj.content, content)

    formatted_content.short_description = "Content"

    def sender_link(self, obj):
        url = reverse("admin:auth_user_change", args=[obj.sender.id])
        return format_html('<a href="{}">{}</a>', url, obj.sender.username)

    sender_link.short_description = "Sender"

    def conversation_link(self, obj):
        url = reverse("admin:messaging_conversation_change", args=[obj.conversation.id])
        return format_html('<a href="{}">{}</a>', url, obj.conversation)

    conversation_link.short_description = "Conversation"

    def read_count(self, obj):
        return obj.read_by.count()

    read_count.short_description = "Read by"


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "emoji", "user_link", "message_preview", "created_at")
    list_filter = ("emoji", "created_at")
    search_fields = ("user__username", "message__content")
    raw_id_fields = ("user", "message")
    readonly_fields = ("created_at",)

    def user_link(self, obj):
        url = reverse("admin:auth_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)

    user_link.short_description = "User"

    def message_preview(self, obj):
        content = (
            obj.message.content[:30] + "..."
            if len(obj.message.content) > 30
            else obj.message.content
        )
        url = reverse("admin:messaging_message_change", args=[obj.message.id])
        return format_html(
            '<a href="{}" title="{}">{}</a>', url, obj.message.content, content
        )

    message_preview.short_description = "Message"
