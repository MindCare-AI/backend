from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.contrib import messages
from .models import (
    CustomUser,
    UserProfile,
    UserPreferences,
    UserSettings,
)


class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "date_joined", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return ("date_joined",) + self.readonly_fields
        return self.readonly_fields


admin.site.register(CustomUser, CustomUserAdmin)


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "timezone", "profile_pic")
    search_fields = ("user__email", "timezone")
    list_filter = ("timezone",)
    ordering = ("-user__created_at",)
    actions = ["set_timezone_automatically"]

    fieldsets = (
        ("Required Information", {"fields": ("user", "timezone")}),
        ("Basic Profile", {"fields": ("bio", "profile_pic"), "classes": ("collapse",)}),
        (
            "Additional Settings",
            {
                "fields": ("privacy_settings", "wearable_data", "therapy_preferences"),
                "classes": ("collapse",),
                "description": "These settings can be updated later",
            },
        ),
    )

    def set_timezone_automatically(self, request, queryset):
        updated = queryset.update(timezone=str(timezone.get_current_timezone()))
        self.message_user(
            request,
            f"{updated} profiles were updated with current timezone.",
            messages.SUCCESS,
        )

    set_timezone_automatically.short_description = "Set timezone to current server time"


admin.site.register(UserProfile, UserProfileAdmin)


class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "language", "notification_settings")
    search_fields = ("user__email", "language")
    list_filter = ("language",)
    ordering = ("-user__created_at",)  # Changed to created_at


admin.site.register(UserPreferences, UserPreferencesAdmin)


class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "theme", "privacy_level")
    search_fields = ("user__email", "theme")
    list_filter = ("theme",)
    ordering = ("-user__created_at",)  # Changed to created_at


admin.site.register(UserSettings, UserSettingsAdmin)
