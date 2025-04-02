# users/serializers/settings.py
from rest_framework import serializers
from users.models.settings import UserSettings
from django.conf import settings
import pytz
import logging

logger = logging.getLogger(__name__)


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            "id",
            "timezone",
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

        mode = value.get("mode", "").upper()
        valid_modes = ["LIGHT", "DARK", "SYSTEM"]
        if mode and mode not in valid_modes:
            raise serializers.ValidationError(
                f"Theme mode must be one of: {', '.join(valid_modes)}"
            )

        return value

    def validate_privacy_settings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Privacy settings must be an object")

        visibility = value.get("profile_visibility", "").upper()
        valid_visibilities = ["PUBLIC", "PRIVATE", "CONTACTS_ONLY"]
        if visibility and visibility not in valid_visibilities:
            raise serializers.ValidationError(
                f"Profile visibility must be one of: {', '.join(valid_visibilities)}"
            )

        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if not data.get("theme_preferences"):
            data["theme_preferences"] = getattr(settings, "USER_SETTINGS", {}).get(
                "DEFAULT_THEME", {"mode": "SYSTEM"}
            )

        if not data.get("privacy_settings"):
            data["privacy_settings"] = getattr(settings, "USER_SETTINGS", {}).get(
                "DEFAULT_PRIVACY", {"profile_visibility": "PUBLIC"}
            )

        return data
