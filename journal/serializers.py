# journal/serializers.py
from rest_framework import serializers
from journal.models import JournalEntry


class JournalEntrySerializer(serializers.ModelSerializer):
    mood_description = serializers.SerializerMethodField()
    date = serializers.DateField(read_only=True)
    word_count = serializers.SerializerMethodField()  # New computed field

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "title",
            "content",
            "mood",
            "mood_description",
            "date",
            "created_at",
            "updated_at",
            "word_count",  # Added word_count field
            "is_private",
            "shared_with_therapist",
            "weather",
            "activities",
        ]
        read_only_fields = ["user", "created_at", "updated_at", "date", "word_count"]

    def get_mood_description(self, obj):
        return obj.get_mood_display() if obj.mood else ""

    def get_word_count(self, obj):
        return len(obj.content.split()) if obj.content else 0

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class JournalEntryDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    mood_description = serializers.SerializerMethodField()
    date = serializers.DateField(read_only=True)
    word_count = serializers.SerializerMethodField()  # New computed field

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "title",
            "content",
            "mood",
            "mood_description",
            "date",
            "created_at",
            "updated_at",
            "word_count",  # Added word_count field
            "is_private",
            "shared_with_therapist",
            "weather",
            "activities",
            "username",
        ]
        read_only_fields = ["user", "created_at", "updated_at", "date", "word_count"]

    def get_mood_description(self, obj):
        return obj.get_mood_display() if obj.mood else ""

    def get_word_count(self, obj):
        return len(obj.content.split()) if obj.content else 0
