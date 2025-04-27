# notifications/serializers.py
from rest_framework import serializers
from .models import Notification, NotificationType


class NotificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationType
        fields = ["id", "name", "description", "default_enabled", "is_global"]


class NotificationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["read"]


class NotificationSerializer(serializers.ModelSerializer):
    notification_type = NotificationTypeSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "read",
            "priority",
            "metadata",
            "created_at",
            "content_type",
            "object_id",
        ]
        read_only_fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "priority",
            "metadata",
            "created_at",
            "content_type",
            "object_id",
        ]
