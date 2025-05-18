# mood/serializers.py
from rest_framework import serializers
from mood.models import MoodLog


class MoodLogSerializer(serializers.ModelSerializer):
    journal_entry_id = serializers.PrimaryKeyRelatedField(
        source="journal_entry", read_only=True
    )
    is_journaled = serializers.SerializerMethodField()

    class Meta:
        model = MoodLog
        fields = [
            "id",
            "user",
            "mood_rating",
            "energy_level",
            "activities",
            "journal_entry_id",
            "is_journaled",
            "logged_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def get_is_journaled(self, obj):
        return obj.journal_entry is not None

    def get_mood_description(self, obj):
        return obj.get_mood_description()

    def create(self, validated_data):
        """Create a mood log"""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class MoodLogDetailSerializer(MoodLogSerializer):
    """Serializer for detailed mood log view"""

    journal_entry_url = serializers.SerializerMethodField()

    class Meta(MoodLogSerializer.Meta):
        fields = MoodLogSerializer.Meta.fields + ["journal_entry_url"]

    def get_journal_entry_url(self, obj):
        if obj.journal_entry:
            return f"/api/v1/journal/entries/{obj.journal_entry.id}/"
        return None


class MoodSummarySerializer(serializers.Serializer):
    """Serializer for mood summary statistics"""

    average_mood = serializers.FloatField()
    count = serializers.IntegerField()
    highest_mood = serializers.FloatField()
    lowest_mood = serializers.FloatField()
    most_common_categories = serializers.ListField(child=serializers.DictField())
    mood_trend = serializers.ListField(child=serializers.DictField())
