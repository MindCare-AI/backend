# mood/admin.py
from django.contrib import admin
from mood.models import MoodLog


@admin.register(MoodLog)
class MoodLogAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "mood_rating",
        "energy_level",
        "activities",
        "logged_at",
        "has_journal",
    ]
    list_filter = ["mood_rating", "energy_level", "logged_at"]
    search_fields = ["user__username", "user__email"]
    filter_horizontal = []
    date_hierarchy = "logged_at"

    fieldsets = [
        ("User Information", {"fields": ["user"]}),
        ("Mood Data", {"fields": ["mood_rating", "energy_level", "activities"]}),
        (
            "Additional Information",
            {"fields": ["notes", "symptoms", "location", "weather"]},
        ),
        ("Timestamps", {"fields": ["logged_at", "created_at", "updated_at"]}),
        ("Journal Connection", {"fields": ["journal_entry"]}),
    ]
    readonly_fields = ["created_at", "updated_at"]

    def has_journal(self, obj):
        """Check if the mood log has an associated journal entry"""
        return obj.journal_entry is not None

    has_journal.boolean = True
    has_journal.short_description = "Has Journal"
