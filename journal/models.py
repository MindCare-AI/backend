#journal/models.py
from django.db import models
from django.utils import timezone
from users.models import CustomUser

class JournalEntry(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="journal_entries")
    title = models.CharField(max_length=255)
    content = models.TextField()
    tags = models.CharField(max_length=255, blank=True, null=True)  # Comma-separated tags
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.title[:30]}"
