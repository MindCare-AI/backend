# users/serializers/preferences.py
from rest_framework import serializers
from users.models.preferences import UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    dark_mode = serializers.BooleanField(
        help_text="Enable or disable dark mode theme",
        label="Dark Mode",
        style={'base_template': 'checkbox.html'}
    )
    
    language = serializers.ChoiceField(
        choices=[
            ('en', 'English'),
            ('fr', 'French'),
            ('es', 'Spanish'),
            ('ar', 'Arabic')
        ],
        help_text="Select your preferred language",
        label="Language",
        style={'base_template': 'select.html'}
    )
    
    notification_preferences = serializers.JSONField(
        help_text="Configure your notification settings (e.g., {'email': true, 'push': false})",
        label="Notification Settings",
        style={'base_template': 'textarea.html', 'rows': 4},
        default=dict
    )

    class Meta:
        model = UserPreferences
        fields = ["dark_mode", "language", "notification_preferences"]
        read_only_fields = ["user"]
        
    def validate_notification_preferences(self, value):
        """Validate notification preferences structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Notification preferences must be an object")
        return value
