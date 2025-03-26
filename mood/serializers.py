#mood/serializers.py
from rest_framework import serializers
from mood.models import MoodLog

class MoodLogSerializer(serializers.ModelSerializer):
    user_username = serializers.SerializerMethodField()

    class Meta:
        model = MoodLog
        fields = ["id", "user", "user_username", "mood_rating", "notes", "logged_at"]
        read_only_fields = ["user", "logged_at"]

    def get_user_username(self, obj):
        return obj.user.username if obj.user else None
