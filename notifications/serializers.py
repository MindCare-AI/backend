# notifications/serializers.py
from rest_framework import serializers
from .models import Notification, NotificationType


class NotificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationType
        fields = ["id", "name", "description", "default_enabled", "is_global"]


class NotificationSerializer(serializers.ModelSerializer):
    notification_type = NotificationTypeSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "read",
            "priority",
            "created_at",
            "notification_type",
            "metadata",
        ]


class NotificationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["read"]
