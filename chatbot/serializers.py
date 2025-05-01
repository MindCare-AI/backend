from rest_framework import serializers
from .models import ChatbotConversation, ChatMessage, ConversationSummary


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "content",
            "sender",
            "sender_name",
            "is_bot",
            "timestamp",
            "message_type",
            "metadata",
            "parent_message",
        ]
        read_only_fields = ["id", "timestamp", "sender_name"]

    def get_sender_name(self, obj):
        if obj.sender:
            return obj.sender.get_full_name() or obj.sender.username
        return None


class ConversationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationSummary
        fields = [
            "id",
            "conversation",
            "created_at",
            "summary_text",
            "key_points",
            "emotional_context",
            "message_count",
        ]
        read_only_fields = ["id", "created_at"]


class ChatbotConversationSerializer(serializers.ModelSerializer):
    recent_messages = ChatMessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()
    latest_summary = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()
    metadata = serializers.JSONField(default=dict)  # Ensure default empty dict

    class Meta:
        model = ChatbotConversation
        fields = [
            "id",
            "user",
            "title",
            "created_at",
            "last_activity",
            "is_active",
            "metadata",
            "last_message",
            "message_count",
            "latest_summary",
            "recent_messages",
            "last_message_at",
        ]
        read_only_fields = ["id", "created_at", "last_activity"]

    def get_last_message(self, obj):
        last_message = obj.messages.order_by("-timestamp").first()
        if last_message:
            return ChatMessageSerializer(last_message).data
        return None

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_latest_summary(self, obj):
        latest_summary = obj.summaries.order_by("-created_at").first()
        if latest_summary:
            return ConversationSummarySerializer(latest_summary).data
        return None

    def get_last_message_at(self, obj):
        last_message = obj.messages.order_by("-timestamp").first()
        if last_message:
            return last_message.timestamp
        return obj.created_at
