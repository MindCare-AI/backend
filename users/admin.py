#users\admin.py
from django.contrib import admin
from .models import (
    UserProfile,
    UserPreferences,
    UserSettings,
)

# Register the UserProfile model in the admin interface
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "timezone", "profile_pic")
    search_fields = ("user__email", "timezone")
    list_filter = ("timezone",)
    ordering = ("-user__date_joined",)

admin.site.register(UserProfile, UserProfileAdmin)

# Register the UserPreferences model in the admin interface
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "language", "notification_settings")
    search_fields = ("user__email", "language")
    list_filter = ("language",)
    ordering = ("-user__date_joined",)

admin.site.register(UserPreferences, UserPreferencesAdmin)

# Register the UserSettings model in the admin interface
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "theme", "privacy_level")
    search_fields = ("user__email", "theme")
    list_filter = ("theme",)
    ordering = ("-user__date_joined",)

admin.site.register(UserSettings, UserSettingsAdmin)
