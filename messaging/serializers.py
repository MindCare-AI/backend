from rest_framework import serializers
from .models import Conversation, Message, Reaction
from django.contrib.auth import get_user_model

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "content",
            "timestamp",
            "is_chatbot",
            "message_type",
            "read_by",
        ]
        read_only_fields = ["sender", "timestamp", "read_by"]
        extra_kwargs = {
            "conversation": {"required": False},
            "message_type": {"required": False},  # Make message_type optional
        }

    def validate(self, data):
        """
        Ensure content is provided.
        """
        if not data.get("content"):
            raise serializers.ValidationError({"content": "This field is required."})

        # Set default message_type if not provided
        if "message_type" not in data:
            data["message_type"] = "text"

        return data


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    participants = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=True
    )

    class Meta:
        model = Conversation
        fields = [
            "id",
            "participants",
            "created_at",
            "messages",
            "last_message",
            "is_active",
            "conversation_type",
        ]
        read_only_fields = ["created_at", "last_message"]

    def validate(self, data):
        """
        Validate that direct messages have exactly 1 additional participant.
        """
        conversation_type = data.get("conversation_type")
        participants = data.get("participants", [])

        if conversation_type == "direct":
            if len(participants) != 1:
                raise serializers.ValidationError(
                    {
                        "participants": "Direct messages require exactly one additional participant."
                    }
                )

        return data

    def create(self, validated_data):
        """
        Create a conversation and add the current user as a participant.
        """
        participants = validated_data.pop("participants")
        conversation = Conversation.objects.create(**validated_data)

        # Add the current user as a participant
        conversation.participants.add(self.context["request"].user)

        # Add the specified participants
        for participant in participants:
            conversation.participants.add(participant)

        return conversation


class GroupChatSerializer(serializers.ModelSerializer):
    moderators = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    participants = serializers.PrimaryKeyRelatedField(
        many=True, queryset=get_user_model().objects.all(), required=False
    )

    class Meta:
        model = Conversation
        fields = ["id", "conversation_type", "participants", "moderators", "created_at"]
        read_only_fields = ["conversation_type", "created_at"]


class ReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reaction
        fields = ["id", "emoji", "user", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class GroupManagementSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    action = serializers.ChoiceField(
        choices=["add-moderator", "remove-moderator", "invite-user", "remove-user"],
        required=True,
    )
