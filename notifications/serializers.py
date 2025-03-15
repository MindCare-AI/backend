# notifications/serializers.py
from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "message",
            "notification_type",
            "is_read",
            "created_at",
            "url",
            "content_type",
            "object_id",
        ]
        read_only_fields = ["created_at"]


class NotificationUpdateSerializer(serializers.Serializer):
    is_read = serializers.BooleanField()
