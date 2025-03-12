# messaging/serializers/group.py
from rest_framework import serializers
from ..models.group import GroupConversation, GroupMessage


class GroupConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupConversation
        fields = [
            "id",
            "name",
            "description",
            "participants",
            "moderators",
            "is_private",
        ]
        read_only_fields = ["moderators"]


class GroupMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessage
        fields = ['id', 'conversation', 'content', 'message_type', 'sender']
        read_only_fields = ['sender']

    def validate(self, attrs):
        conversation = attrs.get('conversation')
        user = self.context['request'].user

        if not conversation:
            raise serializers.ValidationError({"conversation": "This field is required."})

        # Check if conversation exists
        try:
            conversation = GroupConversation.objects.get(id=conversation.id)
        except GroupConversation.DoesNotExist:
            raise serializers.ValidationError({"conversation": "Invalid conversation ID."})

        # Check if user is participant
        if not conversation.participants.filter(id=user.id).exists():
            raise serializers.ValidationError(
                {"conversation": "You are not a participant in this conversation."}
            )

        return attrs
