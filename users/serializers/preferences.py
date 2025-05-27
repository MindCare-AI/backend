# users/serializers/preferences.py
from rest_framework import serializers
from django.db.models import Q
from users.models.preferences import UserPreferences
from notifications.models import NotificationType  # Adjust import as needed


class UserPreferencesSerializer(serializers.ModelSerializer):
    dark_mode = serializers.BooleanField(
        help_text="Enable or disable dark mode theme",
        label="Dark Mode",
        style={"base_template": "checkbox.html"},
    )

    language = serializers.ChoiceField(
        choices=[
            ("en", "English"),
            ("fr", "French"),
            ("es", "Spanish"),
            ("ar", "Arabic"),
        ],
        help_text="Select your preferred language",
        label="Language",
        style={"base_template": "select.html"},
    )

    notification_preferences = serializers.JSONField(
        help_text="Configure your notification settings (e.g., {'email': true, 'push': false})",
        label="Notification Settings",
        style={"base_template": "textarea.html", "rows": 4},
        default=dict,
        required=False,
        allow_null=True,
    )

    disabled_notification_types = serializers.SlugRelatedField(
        many=True,
        slug_field="name",
        queryset=NotificationType.objects.all(),
        required=False,
        help_text="Specific notification types to disable",
    )

    class Meta:
        model = UserPreferences
        fields = [
            "dark_mode",
            "language",
            "email_notifications",
            "in_app_notifications",
            "disabled_notification_types",
            "notification_preferences",
        ]
        read_only_fields = ["user"]

    def validate_notification_preferences(self, value):
        """Validate notification preferences structure"""
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Notification preferences must be an object"
            )
        return value

    def validate(self, data):
        # Ensure users can't disable notifications they don't have access to
        if "disabled_notification_types" in data:
            user = self.context["request"].user
            valid_types = NotificationType.objects.filter(
                Q(is_global=True) | Q(groups__in=user.groups.all())
            ).distinct()
            valid_set = set(valid_types)
            provided_set = set(data["disabled_notification_types"])
            invalid_types = provided_set - valid_set
            if invalid_types:
                invalid_names = ", ".join([nt.name for nt in invalid_types])
                raise serializers.ValidationError(
                    f"Invalid notification types: {invalid_names}"
                )
        return data
