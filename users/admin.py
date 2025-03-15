from django.contrib import admin
from .models import CustomUser, UserPreferences, UserSettings
from django.utils.html import format_html


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "user_type", "date_joined"]
    list_filter = ["user_type", "date_joined"]
    search_fields = ["username", "email"]


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("user", "language", "dark_mode", "get_notification_settings")


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "user_timezone", "get_theme", "get_privacy_level")
    list_filter = ("user_timezone",)
    search_fields = ("user__username", "user__email")

    def get_queryset(self, request):
        """Optimize queries by selecting related user"""
        return super().get_queryset(request).select_related("user")

    def has_add_permission(self, request):
        """Prevent manual creation as settings are auto-created"""
        return False

    def get_theme(self, obj):
        """Display theme settings in a readable format"""
        theme_mode = obj.theme_preferences.get("mode", "system")
        if theme_mode == "dark":
            return format_html('<span style="color: #666;">🌙 Dark</span>')
        elif theme_mode == "light":
            return format_html('<span style="color: #f90;">☀️ Light</span>')
        return format_html("<span>⚙️ System</span>")

    get_theme.short_description = "Theme"
    get_theme.admin_order_field = "theme_preferences"

    def get_privacy_level(self, obj):
        """Display privacy level with an icon"""
        visibility = obj.privacy_settings.get("profile_visibility", "public")
        if visibility == "private":
            return format_html('<span style="color: red;">🔒 Private</span>')
        elif visibility == "friends":
            return format_html('<span style="color: blue;">👥 Friends</span>')
        return format_html('<span style="color: green;">🌐 Public</span>')

    get_privacy_level.short_description = "Privacy"
    get_privacy_level.admin_order_field = "privacy_settings"
