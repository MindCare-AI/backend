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
    sender_name = serializers.CharField(source="sender.username", read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    edit_history = serializers.JSONField(read_only=True)

    class Meta:
        model = GroupMessage
        fields = [
            "id",
            "conversation",
            "content",
            "message_type",
            "sender",
            "sender_name",
            "timestamp",
            "is_edited",
            "edited_at",
            "edit_history",
            "reactions",
            "deleted",
            "deletion_time",
        ]
        read_only_fields = [
            "sender",
            "timestamp",
            "is_edited",
            "edited_at",
            "deleted",
            "deletion_time",
        ]

    def validate(self, attrs):
        """Validate message creation/update"""
        try:
            conversation = attrs.get("conversation")
            request = self.context.get("request")
            if not request or not request.user:
                raise serializers.ValidationError("Authentication required")

            user = request.user

            if not conversation:
                raise serializers.ValidationError(
                    {"conversation": "This field is required"}
                )

            # Ensure conversation exists and user is a participant
            try:
                conversation = GroupConversation.objects.get(
                    id=conversation.id, participants=user
                )
            except GroupConversation.DoesNotExist:
                raise serializers.ValidationError(
                    {"conversation": "Invalid conversation or not a participant"}
                )

            # Check if conversation is archived
            if conversation.archived:
                raise serializers.ValidationError(
                    "Cannot send messages to archived conversations"
                )

            # Only check blocked_users if the conversation has that attribute
            if hasattr(conversation, "blocked_users"):
                if conversation.blocked_users.filter(id=user.id).exists():
                    raise serializers.ValidationError(
                        "You have been blocked from this conversation"
                    )

            # Validate content
            content = attrs.get("content", "").strip()
            if not content:
                raise serializers.ValidationError(
                    {"content": "Message content cannot be empty"}
                )
            if len(content) > settings.GROUP_SETTINGS["MAX_MESSAGE_LENGTH"]:
                raise serializers.ValidationError(
                    {
                        "content": f"Message too long (max {settings.GROUP_SETTINGS['MAX_MESSAGE_LENGTH']} characters)"
                    }
                )

            return attrs

        except Exception as e:
            logger.error(f"Message validation error: {str(e)}")
            raise serializers.ValidationError("Message validation failed")

    def to_representation(self, instance):
        """Override to convert non-serializable objects in reactions"""
        representation = super().to_representation(instance)
        reactions = representation.get("reactions")
        if isinstance(reactions, dict):
            safe_reactions = {}
            for key, value in reactions.items():
                # If value is a CustomUser instance, convert to its id
                if hasattr(value, "id"):
                    safe_reactions[key] = value.id
                else:
                    safe_reactions[key] = value
            representation["reactions"] = safe_reactions
        return representation

    def validate_message_type(self, value):
        allowed = ["text", "system"]
        if value not in allowed:
            raise serializers.ValidationError("Invalid message type for group.")
        return value
