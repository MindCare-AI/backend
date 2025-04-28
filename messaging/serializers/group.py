# messaging/serializers/group.py
from rest_framework import serializers
from django.conf import settings
from ..models.group import GroupConversation, GroupMessage
import logging

logger = logging.getLogger(__name__)


class GroupConversationSerializer(serializers.ModelSerializer):
    participant_count = serializers.IntegerField(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = GroupConversation
        fields = [
            "id",
            "name",
            "description",
            "participants",
            "moderators",
            "is_private",
            "created_at",
            "participant_count",
            "unread_count",
            "last_message",
            "archived",
            "archive_date",
        ]
        read_only_fields = ["moderators", "created_at", "archived", "archive_date"]

    def validate(self, attrs):
        """Validate group creation/update"""
        if self.instance is None:  # Create operation
            # Validate group name
            name = attrs.get("name", "").strip()
            if not name:
                raise serializers.ValidationError({"name": "Group name is required"})
            if len(name) > 100:
                raise serializers.ValidationError({"name": "Group name too long"})

            # Validate participants
            participants = attrs.get("participants", [])
            if len(participants) < 2:
                raise serializers.ValidationError(
                    {"participants": "Group must have at least 2 participants"}
                )
            if (
                len(participants)
                > settings.GROUP_SETTINGS["MAX_PARTICIPANTS_PER_GROUP"]
            ):
                raise serializers.ValidationError(
                    {
                        "participants": f"Maximum {settings.GROUP_SETTINGS['MAX_PARTICIPANTS_PER_GROUP']} participants allowed"
                    }
                )

        return attrs

    def get_last_message(self, obj):
        """Get latest message details"""
        try:
            message = obj.messages.order_by("-timestamp").first()
            if not message:
                return None

            return {
                "id": message.id,
                "content": message.content[:100]
                + ("..." if len(message.content) > 100 else ""),
                "sender_name": message.sender.get_full_name()
                or message.sender.username,
                "timestamp": message.timestamp,
            }
        except Exception as e:
            logger.error(f"Error getting last message: {str(e)}")
            return None


class GroupMessageSerializer(serializers.ModelSerializer):
    MESSAGE_TYPE_CHOICES = (
        ("text", "Text Message"),
        ("system", "System Message"),
    )

    content = serializers.CharField(
        max_length=5000, help_text="Enter the message content"
    )

    conversation = serializers.PrimaryKeyRelatedField(
        queryset=GroupConversation.objects.all(), help_text="Select the conversation"
    )

    message_type = serializers.ChoiceField(choices=MESSAGE_TYPE_CHOICES, default="text")

    edit_history = serializers.ListField(child=serializers.CharField(), default=list)

    media = serializers.FileField(
        required=False,
        allow_null=True,
        help_text="Upload media files (images, videos, PDFs, etc.)",
    )

    class Meta:
        model = GroupMessage
        fields = [
            "id",
            "conversation",
            "content",
            "message_type",
            "sender",
            "timestamp",
            "edit_history",
            "media",
        ]
        read_only_fields = ["id", "sender", "timestamp"]


class AddParticipantSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(help_text="ID of the user to add as a participant.")


class EditHistorySerializer(serializers.Serializer):
    editor = serializers.CharField(help_text="The user who edited the message.")
    timestamp = serializers.DateTimeField(help_text="The time the edit was made.")
    previous_content = serializers.CharField(help_text="The content of the message before the edit.")


class GroupMessageSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessage
        fields = ["id", "content", "sender", "timestamp", "conversation"]


class GroupConversationSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupConversation
        fields = ["id", "name", "description", "participant_count"]
