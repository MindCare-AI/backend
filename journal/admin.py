# journal/admin.py
from django.contrib import admin
from journal.models import JournalEntry


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["title", "content", "tags"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        ("Basic Information", {"fields": ["user", "title", "content"]}),
        ("Metadata", {"fields": ["tags"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
