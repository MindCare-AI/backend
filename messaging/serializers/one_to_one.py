# messaging/serializers/one_to_one.py
from rest_framework import serializers
from ..models.one_to_one import OneToOneConversation, OneToOneMessage
import logging

logger = logging.getLogger(__name__)


class OneToOneConversationSerializer(serializers.ModelSerializer):
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    other_user_name = serializers.SerializerMethodField()

    class Meta:
        model = OneToOneConversation
        fields = [
            "id",
            "participants",
            "created_at",
            "unread_count",
            "last_message",
            "other_participant",
            "other_user_name",
        ]
        read_only_fields = ["created_at", "unread_count"]

    def validate_participants(self, value):
        try:
            request = self.context.get("request")
            if not request:
                raise serializers.ValidationError("Request context is missing.")

            current_user = request.user
            if len(value) != 1:
                raise serializers.ValidationError(
                    "Must include exactly one other participant."
                )

            other_user = value[0]
            if current_user == other_user:
                raise serializers.ValidationError(
                    "Cannot create conversation with yourself."
                )

            # Check user types
            user_types = {current_user.user_type, other_user.user_type}
            if user_types != {"patient", "therapist"}:
                raise serializers.ValidationError(
                    "Conversation must have one patient and one therapist."
                )

            # Check existing conversation
            if self._conversation_exists(current_user, other_user):
                raise serializers.ValidationError(
                    "Conversation already exists between these users."
                )

            return value

        except Exception as e:
            logger.error(f"Error validating participants: {str(e)}")
            raise serializers.ValidationError("Invalid participants")

    def _conversation_exists(self, user1, user2):
        """Check if conversation exists between two users"""
        return (
            OneToOneConversation.objects.filter(participants=user1)
            .filter(participants=user2)
            .exists()
        )

    def get_last_message(self, obj):
        """Get the last message in the conversation."""
        try:
            message = obj.messages.last()
            if message:
                return {
                    "id": message.id,
                    "content": message.content,
                    "timestamp": message.timestamp,
                    "sender_id": message.sender_id,
                    "sender_name": message.sender.username,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting last message: {str(e)}")
            return None

    def get_other_participant(self, obj):
        """Get details of the other participant."""
        try:
            request = self.context.get("request")
            if not request:
                return None

            other_user = obj.participants.exclude(id=request.user.id).first()
            if not other_user:
                return None

            return {
                "id": other_user.id,
                "username": other_user.username,
                "user_type": other_user.user_type,
            }
        except Exception as e:
            logger.error(f"Error getting other participant: {str(e)}")
            return None

    def get_other_user_name(self, obj):
        """Get the full name or username of the other participant."""
        request = self.context.get("request")
        if not request:
            return None
        other_user = obj.participants.exclude(id=request.user.id).first()
        if other_user:
            return other_user.get_full_name() or other_user.username
        return None


class OneToOneMessageSerializer(serializers.ModelSerializer):
    MESSAGE_TYPE_CHOICES = (
        ("text", "Text Message"),
        ("system", "System Message"),
    )

    content = serializers.CharField(
        max_length=5000, help_text="Enter the message content"
    )

    conversation = serializers.PrimaryKeyRelatedField(
        queryset=OneToOneConversation.objects.all(), help_text="Select the conversation"
    )

    message_type = serializers.ChoiceField(choices=MESSAGE_TYPE_CHOICES, default="text")

    sender_name = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = OneToOneMessage
        fields = [
            "id",
            "conversation",
            "content",
            "message_type",
            "sender",
            "sender_name",
            "timestamp",
        ]
        read_only_fields = ["id", "sender", "sender_name", "timestamp"]

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError(
                "Authenticated user is required to send a message."
            )

        validated_data["sender"] = (
            request.user
        )  # Set the sender to the authenticated user
        return super().create(validated_data)
