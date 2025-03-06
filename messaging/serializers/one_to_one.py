# messaging/serializers/one_to_one.py
from rest_framework import serializers
from ..models.one_to_one import OneToOneConversation, OneToOneMessage


class OneToOneConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OneToOneConversation
        fields = ["id", "participants", "created_at", "is_active"]
        read_only_fields = ["created_at"]


class OneToOneMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OneToOneMessage
        fields = ["id", "content", "sender", "timestamp", "conversation"]
        read_only_fields = ["sender", "timestamp"]
