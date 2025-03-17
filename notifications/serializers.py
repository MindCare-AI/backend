# notifications/serializers.py
from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""

    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "created_at",
            "priority",
            "link",
            "category",
        ]

    def get_unread_count(self, obj):
        return Notification.objects.filter(user=obj.user, is_read=False).count()


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for NotificationPreference model"""

    class Meta:
        model = NotificationPreference
        fields = [
            "email_notifications",
            "in_app_notifications",
            "disabled_notification_types",
        ]


class NotificationBulkActionSerializer(serializers.Serializer):
    """Serializer for bulk actions on notifications"""

    notification_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True
    )
    action = serializers.ChoiceField(
        choices=["mark_read", "delete", "archive"]
    )  # Added 'archive'


class NotificationCountSerializer(serializers.Serializer):
    """Serializer for notification counts"""

    total = serializers.IntegerField()
    unread = serializers.IntegerField()
    unread_by_category = serializers.DictField(child=serializers.IntegerField())


class MarkAllReadSerializer(serializers.Serializer):
    """Serializer for marking all notifications as read"""

    pass
