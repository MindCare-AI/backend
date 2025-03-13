from django.contrib import admin
from .models import CustomUser, UserPreferences, UserSettings, PatientProfile, TherapistProfile


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "user_type", "date_joined"]
    list_filter = ["user_type", "date_joined"]
    search_fields = ["username", "email"]


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user', 'language', 'dark_mode', 'get_notification_settings')


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'timezone', 'get_theme', 'get_privacy_level')
    list_filter = ('timezone',)  # Remove 'theme'
