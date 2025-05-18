# journal/admin.py
from django.contrib import admin
from journal.models import JournalEntry, JournalCategory


@admin.register(JournalCategory)
class JournalCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "created_at", "entries_count"]
    list_filter = ["created_at"]
    search_fields = ["name", "user__username"]
    readonly_fields = ["created_at", "updated_at"]

    def entries_count(self, obj):
        return obj.entries.count()

    entries_count.short_description = "Entries"


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "category", "created_at"]
    list_filter = ["created_at", "category"]
    search_fields = ["title", "content", "tags"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        ("Basic Information", {"fields": ["user", "title", "content", "category"]}),
        ("Metadata", {"fields": ["tags"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
