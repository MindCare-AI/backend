# Register your models here.
from django.contrib import admin
from .models import CustomUser, AuthToken, UserDevice, UserProfile, UserPreferences, UserSettings

# Register the CustomUser model to the admin interface
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'username', 'is_active', 'created_at')
    search_fields = ('email', 'username')
    list_filter = ('is_active',)
    ordering = ('-created_at',)
    fieldsets = (
        (None, {
            'fields': ('email', 'username', 'password', 'is_active')
        }),
        ('Permissions', {
            'fields': ('is_staff', 'is_superuser')
        }),
        ('Dates', {
            'fields': ('created_at',)
        }),
    )
    filter_horizontal = ()

admin.site.register(CustomUser, CustomUserAdmin)

# Register the AuthToken model to the admin interface
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'device_id', 'created_at')
    search_fields = ('user__email', 'device_id')
    list_filter = ('user',)
    ordering = ('-created_at',)

admin.site.register(AuthToken, AuthTokenAdmin)

# Register the UserDevice model to the admin interface
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'device_type', 'last_login')
    search_fields = ('user__email', 'device_id', 'device_type')
    list_filter = ('device_type',)
    ordering = ('-last_login',)

admin.site.register(UserDevice, UserDeviceAdmin)

# Register the UserProfile model to the admin interface
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'timezone', 'profile_pic')
    search_fields = ('user__email', 'timezone')
    list_filter = ('timezone',)
    ordering = ('-user__created_at',)

admin.site.register(UserProfile, UserProfileAdmin)

# Register the UserPreferences model to the admin interface
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'language', 'notification_settings')
    search_fields = ('user__email', 'language')
    list_filter = ('language',)
    ordering = ('-user__created_at',)

admin.site.register(UserPreferences, UserPreferencesAdmin)

# Register the UserSettings model to the admin interface
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'theme', 'privacy_level')
    search_fields = ('user__email', 'theme')
    list_filter = ('theme',)
    ordering = ('-user__created_at',)

admin.site.register(UserSettings, UserSettingsAdmin)
