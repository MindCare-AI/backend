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


class BulkDeleteNotificationSerializer(serializers.Serializer):
    """Serializer for bulk deleting notifications"""
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text="List of notification IDs to delete (e.g., [1, 2, 3])"
    )
    
    class Meta:
        fields = ['notification_ids']

    def validate_notification_ids(self, ids):
        """Validate notification IDs belong to the user"""
        user = self.context['request'].user
        
        # Check if all IDs exist and belong to the user
        user_notification_ids = set(Notification.objects.filter(
            user=user,
            id__in=ids
        ).values_list('id', flat=True))
        
        invalid_ids = set(ids) - user_notification_ids
        if invalid_ids:
            raise serializers.ValidationError(
                f"Notifications with IDs {list(invalid_ids)} do not exist or don't belong to you"
            )
        
        return ids

    def to_representation(self, instance):
        """Custom representation for better browsable API display"""
        return {
            "notification_ids": instance.get("notification_ids", []),
            "instructions": "Submit a POST request with a list of notification IDs to delete them"
        }
