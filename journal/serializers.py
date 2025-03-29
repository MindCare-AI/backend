# journal/serializers.py
from rest_framework import serializers
from journal.models import JournalEntry


class JournalEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalEntry
        fields = ["id", "user", "title", "content", "tags", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]
