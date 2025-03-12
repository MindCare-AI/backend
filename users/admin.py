from django.contrib import admin
from .models import (
    CustomUser,
    UserPreferences,
    UserSettings,
)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "user_type", "date_joined"]
    list_filter = ["user_type", "date_joined"]
    search_fields = ["username", "email"]


class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "language", "notification_settings")
    search_fields = ("user__email", "language")
    list_filter = ("language",)
    ordering = ("-user__created_at",)


admin.site.register(UserPreferences, UserPreferencesAdmin)


class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "theme", "privacy_level")
    search_fields = ("user__email", "theme")
    list_filter = ("theme",)
    ordering = ("-user__created_at",)


admin.site.register(UserSettings, UserSettingsAdmin)
