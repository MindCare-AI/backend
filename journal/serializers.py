# journal/serializers.py
from rest_framework import serializers
from journal.models import JournalEntry


class JournalEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'title', 'content',
            'mood', 'created_at', 'updated_at', 'is_private',
            'shared_with_therapist', 'weather', 'activities'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class JournalEntryDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = JournalEntry
        fields = [
            'id', 'title', 'content',
            'mood', 'created_at', 'updated_at', 'is_private',
            'shared_with_therapist', 'weather', 'activities', 'username'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']
