# messaging/serializers/chatbot.py
from rest_framework import serializers
from ..models.chatbot import ChatbotConversation, ChatbotMessage


class ChatbotConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotConversation
        fields = ["id", "user", "created_at"]
        read_only_fields = ["user", "created_at"]


class ChatbotMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotMessage
        fields = ["id", "content", "sender", "timestamp", "is_bot"]
        read_only_fields = ["sender", "timestamp", "is_bot"]
