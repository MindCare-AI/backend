from rest_framework import serializers
from .models import ChatbotConversation, ChatbotMessage


class ChatbotConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotConversation
        fields = ["id", "user", "created_at"]
        read_only_fields = ["user", "created_at"]


class ChatbotMessageSerializer(serializers.ModelSerializer):
    content = serializers.CharField(
        style={
            "base_template": "textarea.html",
            "rows": 3,
            "placeholder": "Enter your message to the chatbot...",
        },
        help_text="Enter your message",
        max_length=1000,
    )

    class Meta:
        model = ChatbotMessage
        fields = ["id", "content", "sender", "timestamp", "is_bot"]
        read_only_fields = ["sender", "timestamp", "is_bot"]