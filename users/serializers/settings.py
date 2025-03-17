# users/serializers/settings.py
from rest_framework import serializers
from users.models.settings import UserSettings
from django.conf import settings
import pytz
import logging

logger = logging.getLogger(__name__)


class UserSettingsSerializer(serializers.ModelSerializer):
    THEME_MODES = [("LIGHT", "Light"), ("DARK", "Dark"), ("SYSTEM", "System")]

    VISIBILITY_LEVELS = [
        ("PUBLIC", "Public"),
        ("PRIVATE", "Private"),
        ("CONTACTS_ONLY", "Contacts Only"),
    ]

    timezone = serializers.CharField(
        max_length=50,
        required=False,
        default=settings.TIME_ZONE,
        help_text="User's preferred timezone (e.g., 'UTC', 'America/New_York')",
    )
    theme_mode = serializers.ChoiceField(
        choices=THEME_MODES, default="SYSTEM", help_text="User's preferred theme mode"
    )
    profile_visibility = serializers.ChoiceField(
        choices=VISIBILITY_LEVELS,
        default="PUBLIC",
        help_text="User's profile visibility setting",
    )
    theme_preferences = serializers.DictField(
        required=False,
        default=dict,
        help_text="User's theme preferences including mode and color scheme",
    )
    privacy_settings = serializers.DictField(
        required=False,
        default=dict,
        help_text="User's privacy configuration including visibility and status",
    )

    class Meta:
        model = UserSettings
        fields = [
            "id",
            "timezone",
            "theme_mode",
            "profile_visibility",
            "theme_preferences",
            "privacy_settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_timezone(self, value):
        try:
            if value not in pytz.all_timezones:
                raise serializers.ValidationError(
                    f"Invalid timezone. Must be one of: {', '.join(pytz.common_timezones)}"
                )
            return value
        except Exception as e:
            logger.error(f"Timezone validation error: {str(e)}")
            raise serializers.ValidationError("Invalid timezone format")

    def validate_theme_preferences(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Theme preferences must be an object")

        required_keys = {"mode", "color_scheme"}
        missing_keys = required_keys - set(value.keys())
        if missing_keys:
            raise serializers.ValidationError(
                f"Missing required theme preferences: {', '.join(missing_keys)}"
            )

        valid_modes = settings.USER_SETTINGS["THEME_MODES"]
        if value["mode"] not in valid_modes:
            raise serializers.ValidationError(
                f"Invalid theme mode. Must be one of: {', '.join(valid_modes)}"
            )

        return value

    def validate_privacy_settings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Privacy settings must be an object")

        required_keys = {"profile_visibility", "show_online_status"}
        missing_keys = required_keys - set(value.keys())
        if missing_keys:
            raise serializers.ValidationError(
                f"Missing required privacy settings: {', '.join(missing_keys)}"
            )

        valid_visibilities = settings.USER_SETTINGS["PRIVACY_LEVELS"]
        if value["profile_visibility"] not in valid_visibilities:
            raise serializers.ValidationError(
                f"Invalid visibility level. Must be one of: {', '.join(valid_visibilities)}"
            )

        if not isinstance(value["show_online_status"], bool):
            raise serializers.ValidationError("show_online_status must be a boolean")

        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if not data.get("theme_preferences"):
            data["theme_preferences"] = settings.USER_SETTINGS["DEFAULT_THEME"]

        if not data.get("privacy_settings"):
            data["privacy_settings"] = settings.USER_SETTINGS["DEFAULT_PRIVACY"]

        return data
