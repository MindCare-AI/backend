# messaging/serializers/one_to_one.py
from rest_framework import serializers
from ..models.one_to_one import OneToOneConversation, OneToOneMessage


class OneToOneConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OneToOneConversation
        fields = ["id", "participants", "created_at"]
        read_only_fields = ["created_at"]

    def validate_participants(self, value):
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context is missing.")
        current_user = request.user
        # Expect exactly one participant from the client (the other participant)
        if len(value) != 1:
            raise serializers.ValidationError(
                "Must include exactly one other participant."
            )
        # Optionally, check that the provided participant is not the current user
        if current_user in value:
            raise serializers.ValidationError(
                "Do not include yourself in participants."
            )
        # Check that the two user types are complementary (one patient, one therapist)
        user_types = {p.user_type for p in value} | {current_user.user_type}
        if user_types != {"patient", "therapist"}:
            raise serializers.ValidationError(
                "Conversation must have one patient and one therapist."
            )
        return value


class OneToOneMessageSerializer(serializers.ModelSerializer):
    # Ensure reactions is never null
    reactions = serializers.JSONField(required=False, allow_null=False, default=dict)

    class Meta:
        model = OneToOneMessage
        fields = ["id", "content", "sender", "timestamp", "conversation", "reactions"]
        read_only_fields = ["sender", "timestamp"]

    def validate_reactions(self, value):
        # If client sends null, convert it to an empty dict.
        if value is None:
            return {}
        return value
