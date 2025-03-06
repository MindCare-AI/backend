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
        fields = [
            "id",
            "content",
            "sender",
            "timestamp",
            "conversation",
            "message_type",
        ]
        read_only_fields = ["sender", "timestamp"]
