# journal/serializers.py
from rest_framework import serializers
from journal.models import JournalEntry, JournalCategory


class JournalCategorySerializer(serializers.ModelSerializer):
    entries_count = serializers.SerializerMethodField()
    title = serializers.CharField(source="name", read_only=True)  # Add this for frontend compatibility

    class Meta:
        model = JournalCategory
        fields = ["id", "name", "title", "color", "icon", "created_at", "updated_at", "entries_count"]
        read_only_fields = ["created_at", "updated_at", "entries_count", "title"]

    def get_entries_count(self, obj):
        return obj.entries.count()

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class JournalEntrySerializer(serializers.ModelSerializer):
    mood_description = serializers.SerializerMethodField()
    date = serializers.DateField(read_only=True)
    word_count = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "content",
            "mood",
            "mood_description",
            "date",
            "created_at",
            "updated_at",
            "word_count",
            "is_private",
            "shared_with_therapist",
            "weather",
            "activities",
            "category",
            "category_name",
        ]
        read_only_fields = [
            "user",
            "created_at",
            "updated_at",
            "date",
            "word_count",
            "category_name",
        ]

    def get_mood_description(self, obj):
        return obj.get_mood_display() if obj.mood else ""

    def get_word_count(self, obj):
        return len(obj.content.split()) if obj.content else 0

    def get_category_name(self, obj):
        return obj.category.name if obj.category else ""

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class JournalEntryDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    mood_description = serializers.SerializerMethodField()
    date = serializers.DateField(read_only=True)
    word_count = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "content",
            "mood",
            "mood_description",
            "date",
            "created_at",
            "updated_at",
            "word_count",
            "is_private",
            "shared_with_therapist",
            "weather",
            "activities",
            "username",
            "category",
            "category_name",
        ]
        read_only_fields = [
            "user",
            "created_at",
            "updated_at",
            "date",
            "word_count",
            "category_name",
        ]

    def get_mood_description(self, obj):
        return obj.get_mood_display() if obj.mood else ""

    def get_word_count(self, obj):
        return len(obj.content.split()) if obj.content else 0

    def get_category_name(self, obj):
        return obj.category.name if obj.category else ""
