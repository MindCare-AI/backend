# chatbot/serializers.py
from rest_framework import serializers
from .models import ChatbotConversation, ChatMessage, ConversationSummary
import logging

logger = logging.getLogger(__name__)


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField(read_only=True)
    chatbot_method = serializers.SerializerMethodField(read_only=True)  # New field

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "content",
            "sender",
            "sender_name",
            "is_bot",
            "timestamp",
            "message_type",
            "metadata",
            "parent_message",
            "chatbot_method",  # Include new field in the response
        ]
        read_only_fields = ["id", "timestamp", "sender_name", "chatbot_method"]

    def get_sender_name(self, obj):
        if obj.sender:
            return obj.sender.get_full_name() or obj.sender.username
        return "Bot" if obj.is_bot else "Unknown"

    def get_chatbot_method(self, obj):
        if obj.is_bot:
            # If the metadata contains a therapy recommendation from the RAG,
            # return its 'approach'. Otherwise, fallback to a default.
            rec = obj.metadata.get("therapy_recommendation") if obj.metadata else None
            if rec and rec.get("approach"):
                return rec.get("approach")
            return "Not determined"
        return None


class ConversationSummarySerializer(serializers.ModelSerializer):
    """Serializer for conversation summaries"""
    
    class Meta:
        model = ConversationSummary
        fields = [
            "id",
            "conversation_id", 
            "user",
            "start_message",
            "end_message", 
            "created_at",
            "summary_text",
            "key_points",
            "emotional_context",
            "message_count",
            "metadata"
        ]
        read_only_fields = ["id", "created_at"]


class ChatbotConversationSerializer(serializers.ModelSerializer):
    """Serializer for chatbot conversations with enhanced functionality"""
    
    recent_messages = ChatMessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()
    latest_summary = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()
    metadata = serializers.HiddenField(default=dict)  # Hide metadata from browsable API
    participants = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = ChatbotConversation
        fields = [
            "id",
            "user",
            "title",
            "created_at",
            "last_activity",
            "is_active",
            "metadata",  # Still included in the API response but hidden in browsable API
            "last_message",
            "message_count",
            "latest_summary",
            "recent_messages",
            "last_message_at",
            "participants",
        ]
        read_only_fields = ["id", "created_at", "last_activity"]

    def get_last_message(self, obj):
        """Get the last message in the conversation"""
        try:
            last_message = obj.messages.order_by('-timestamp').first()
            if last_message:
                return {
                    "id": last_message.id,
                    "content": last_message.content[:100] + ("..." if len(last_message.content) > 100 else ""),
                    "is_bot": last_message.is_bot,
                    "timestamp": last_message.timestamp,
                    "sender_name": last_message.sender.get_full_name() or last_message.sender.username if last_message.sender else "Bot"
                }
            return None
        except Exception as e:
            logger.error(f"Error getting last message: {str(e)}")
            return None

    def get_message_count(self, obj):
        """Get the total number of messages in this conversation"""
        try:
            return obj.messages.count()
        except Exception as e:
            logger.error(f"Error getting message count: {str(e)}")
            return 0

    def get_latest_summary(self, obj):
        # Check if the model has a summaries relationship
        if hasattr(obj, 'summaries'):
            latest_summary = obj.summaries.order_by("-created_at").first()
            if latest_summary:
                return ConversationSummarySerializer(latest_summary).data
        return None

    def get_last_message_at(self, obj):
        last_message = obj.messages.order_by("-timestamp").first()
        if last_message:
            return last_message.timestamp
        return obj.created_at

    def validate_title(self, value):
        """Validate the conversation title"""
        if value and len(value.strip()) == 0:
            raise serializers.ValidationError("Title cannot be empty or just whitespace")
        
        if value and len(value) > 255:
            raise serializers.ValidationError("Title cannot be longer than 255 characters")
        
        return value.strip() if value else value
    
    def update(self, instance, validated_data):
        """Custom update method to handle title changes"""
        # Update the title if provided
        if 'title' in validated_data:
            instance.title = validated_data['title']
        
        # Update metadata if provided
        if 'metadata' in validated_data:
            # Merge with existing metadata instead of replacing
            existing_metadata = instance.metadata or {}
            new_metadata = validated_data['metadata'] or {}
            instance.metadata = {**existing_metadata, **new_metadata}
        
        # Update is_active if provided
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']
        
        instance.save()
        return instance


class ChatbotConversationUpdateSerializer(serializers.ModelSerializer):
    """Dedicated serializer for updating conversation details"""
    
    class Meta:
        model = ChatbotConversation
        fields = ["title", "metadata", "is_active"]
    
    def validate_title(self, value):
        """Validate the conversation title"""
        if value is not None and len(value.strip()) == 0:
            raise serializers.ValidationError("Title cannot be empty or just whitespace")
        
        if value and len(value) > 255:
            raise serializers.ValidationError("Title cannot be longer than 255 characters")
        
        return value.strip() if value else value


class ChatbotConversationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing conversations"""
    
    message_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatbotConversation
        fields = [
            "id",
            "title", 
            "created_at",
            "last_activity",
            "is_active",
            "message_count",
            "last_message_preview"
        ]
    
    def get_message_count(self, obj):
        """Get message count efficiently"""
        return getattr(obj, 'message_count', 0)
    
    def get_last_message_preview(self, obj):
        """Get a preview of the last message"""
        try:
            last_message = obj.messages.order_by('-timestamp').first()
            if last_message:
                content = last_message.content
                preview = content[:50] + "..." if len(content) > 50 else content
                return {
                    "preview": preview,
                    "is_bot": last_message.is_bot,
                    "timestamp": last_message.timestamp
                }
            return None
        except Exception:
            return None
