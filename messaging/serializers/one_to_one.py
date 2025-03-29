# messaging/serializers/one_to_one.py
from rest_framework import serializers
from ..models.one_to_one import OneToOneConversation, OneToOneMessage
import logging
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class OneToOneConversationSerializer(serializers.ModelSerializer):
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    other_user_name = serializers.SerializerMethodField()  # New field

    class Meta:
        model = OneToOneConversation
        fields = [
            "id",
            "participants",
            "created_at",
            "unread_count",
            "last_message",
            "other_participant",
            "other_user_name",  # Include it in the serializer output
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
        """Get the last message in conversation"""
        try:
            message = obj.messages.last()
            if message:
                return {
                    "content": message.content,
                    "timestamp": message.timestamp,
                    "sender_id": message.sender_id,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting last message: {str(e)}")
            return None

    def get_other_participant(self, obj):
        """Get details of the other participant"""
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
        request = self.context.get("request")
        if not request:
            return None
        other_user = obj.participants.exclude(id=request.user.id).first()
        if other_user:
            return other_user.get_full_name() or other_user.username
        return None


class OneToOneMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.username", read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    message_type = serializers.CharField(required=False, default="text")
    read_by = serializers.PrimaryKeyRelatedField(
        many=True, queryset=get_user_model().objects.all(), required=False
    )
    reactions = serializers.JSONField(required=False, allow_null=True, default=dict)
    formatted_reactions = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OneToOneMessage
        fields = [
            "id",
            "content",
            "sender",
            "sender_name",
            "timestamp",
            "conversation",
            "message_type",
            "reactions",
            "formatted_reactions",
            "is_edited",
            "read_by",
        ]
        read_only_fields = [
            "sender",
            "timestamp",
            "sender_name",
            "is_edited",
            "formatted_reactions",
        ]

    def validate_content(self, value):
        """Validate message content"""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")

        if len(value) > 5000:  # Maximum message length
            raise serializers.ValidationError("Message too long")

        return value.strip()

    def validate_reactions(self, value):
        """Validate message reactions"""
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise serializers.ValidationError("Reactions must be a dictionary")

        # Validate reaction types and values
        valid_reactions = {"like", "heart", "smile", "thumbsup"}

        for reaction_type, user_ids in value.items():
            # Check reaction type
            if reaction_type not in valid_reactions:
                raise serializers.ValidationError(
                    f"Invalid reaction type: {reaction_type}"
                )

            # Check user IDs list format
            if not isinstance(user_ids, list):
                raise serializers.ValidationError(
                    f"Reaction '{reaction_type}' must contain a list of user IDs"
                )

            # Validate each user ID is a string
            for user_id in user_ids:
                if not isinstance(user_id, str):
                    raise serializers.ValidationError(
                        f"User ID must be a string, got {type(user_id).__name__}"
                    )

        return value

    def validate_reaction(self, value):
        """Validate a single reaction"""
        valid_reactions = {"like", "heart", "smile", "thumbsup"}

        if not isinstance(value, str):
            raise serializers.ValidationError("Reaction must be a string")

        if value not in valid_reactions:
            raise serializers.ValidationError(
                f"Invalid reaction. Must be one of: {', '.join(valid_reactions)}"
            )

        return value

    def add_reaction(self, user, reaction_type):
        """Add a reaction from a user"""
        # Validate reaction
        self.validate_reaction(reaction_type)

        # Get instance and its current reactions
        instance = self.instance
        reactions = instance.reactions or {}

        # Initialize the reaction type list if it doesn't exist
        if reaction_type not in reactions:
            reactions[reaction_type] = []

        # Add user ID if not already present
        user_id = str(user.id)
        if user_id not in reactions[reaction_type]:
            reactions[reaction_type].append(user_id)

        # Update instance
        instance.reactions = reactions
        instance.save(update_fields=["reactions"])

        return reactions

    def remove_reaction(self, user, reaction_type=None):
        """Remove a user's reaction"""
        instance = self.instance
        reactions = instance.reactions or {}
        user_id = str(user.id)

        # If reaction type specified, remove from just that type
        if reaction_type:
            if reaction_type in reactions and user_id in reactions[reaction_type]:
                reactions[reaction_type].remove(user_id)
                # Remove empty lists
                if not reactions[reaction_type]:
                    del reactions[reaction_type]
        else:
            # Remove from all reaction types
            for r_type in list(reactions.keys()):
                if user_id in reactions[r_type]:
                    reactions[r_type].remove(user_id)
                    # Remove empty lists
                    if not reactions[r_type]:
                        del reactions[r_type]

        # Update instance
        instance.reactions = reactions
        instance.save(update_fields=["reactions"])

        return reactions

    def get_formatted_reactions(self, obj):
        """Format reactions for display with user details"""
        try:
            reactions = obj.reactions or {}
            formatted = {}

            from django.contrib.auth import get_user_model

            User = get_user_model()

            # Process each reaction type
            for reaction_type, user_ids in reactions.items():
                # Get user details for each ID
                user_objects = User.objects.filter(id__in=user_ids)
                user_map = {str(user.id): user for user in user_objects}

                formatted[reaction_type] = [
                    {
                        "user_id": user_id,
                        "username": user_map.get(user_id).username
                        if user_id in user_map
                        else "Unknown",
                        "name": (
                            user_map.get(user_id).get_full_name()
                            or user_map.get(user_id).username
                        )
                        if user_id in user_map
                        else "Unknown",
                    }
                    for user_id in user_ids
                ]

            return formatted

        except Exception as e:
            logger.error(f"Error formatting reactions: {str(e)}")
            return {}

    def validate_conversation(self, value):
        """Validate conversation access"""
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context is missing")

        if not value.participants.filter(id=request.user.id).exists():
            raise serializers.ValidationError(
                "You are not a participant in this conversation"
            )

        return value

    def get_read_by(self, obj):
        """Get list of users who have read the message"""
        try:
            return [
                {
                    "id": user.id,
                    "username": user.username,
                    "read_at": obj.read_receipts.get(str(user.id)),
                }
                for user in obj.read_by.all()
            ]
        except Exception as e:
            logger.error(f"Error getting read receipts: {str(e)}")
            return []
