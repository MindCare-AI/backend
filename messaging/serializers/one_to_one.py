# messaging/serializers/one_to_one.py
from rest_framework import serializers
from ..models.one_to_one import OneToOneConversation, OneToOneMessage
from django.utils import timezone
import logging

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
    message_type = serializers.CharField(required=False, default="text")  # New field
    read_by = serializers.SerializerMethodField()
    reactions = serializers.JSONField(required=False, allow_null=False, default=dict)

    class Meta:
        model = OneToOneMessage
        fields = [
            "id",
            "content",
            "sender",
            "sender_name",
            "timestamp",
            "conversation",
            "message_type",  # Include message_type in the output
            "reactions",
            "is_edited",
            "read_by",
        ]
        read_only_fields = ["sender", "timestamp", "sender_name", "is_edited"]

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

        # Validate reaction types
        valid_reactions = {"like", "heart", "smile", "thumbsup"}
        for reaction_type in value.keys():
            if reaction_type not in valid_reactions:
                raise serializers.ValidationError(
                    f"Invalid reaction type: {reaction_type}"
                )

        return value

    def validate_reaction(self, value):
        """Validate a single reaction"""
        valid_reactions = {'like', 'heart', 'smile', 'thumbsup'}
        
        if not isinstance(value, str):
            raise serializers.ValidationError("Reaction must be a string")
            
        if value not in valid_reactions:
            raise serializers.ValidationError(
                f"Invalid reaction. Must be one of: {', '.join(valid_reactions)}"
            )
            
        return value
    
    def add_reaction(self, user, reaction_type):
        """Add or update a reaction"""
        # Validate reaction
        self.validate_reaction(reaction_type)
        
        # Get current reactions or initialize empty dict
        reactions = self.validated_data.get('reactions', {})
        
        # Add/update user's reaction
        reactions[str(user.id)] = {
            'type': reaction_type,
            'timestamp': timezone.now().isoformat(),
            'user': {
                'id': user.id,
                'name': user.get_full_name() or user.username
            }
        }
        
        self.validated_data['reactions'] = reactions
        return reactions
    
    def remove_reaction(self, user):
        """Remove a user's reaction"""
        reactions = self.validated_data.get('reactions', {})
        user_id = str(user.id)
        
        if user_id in reactions:
            del reactions[user_id]
            self.validated_data['reactions'] = reactions
            
        return reactions

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
