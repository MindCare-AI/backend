# users\admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser,
    UserProfile,
    UserPreferences,
    UserSettings,
)

class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'created_at')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'created_at')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('created_at',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('email', 'created_at',)}),
    )
    
    
    verbose_name = 'user'
    verbose_name_plural = 'users'

admin.site.register(CustomUser, CustomUserAdmin)

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "timezone", "profile_pic")
    search_fields = ("user__email", "timezone")
    list_filter = ("timezone",)
    ordering = ("-user__date_joined",)

admin.site.register(UserProfile, UserProfileAdmin)

class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "language", "notification_settings")
    search_fields = ("user__email", "language")
    list_filter = ("language",)
    ordering = ("-user__date_joined",)

admin.site.register(UserPreferences, UserPreferencesAdmin)

class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "theme", "privacy_level")
    search_fields = ("user__email", "theme")
    list_filter = ("theme",)
    ordering = ("-user__date_joined",)

admin.site.register(UserSettings, UserSettingsAdmin)
