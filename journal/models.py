# journal/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class JournalCategory(models.Model):
    """Model for categorizing journal entries"""

    name = models.CharField(max_length=200)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_categories",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Journal Categories"
        ordering = ["name"]
        unique_together = ["name", "user"]  # Ensure categories are unique per user

    def __str__(self):
        return f"{self.name} (by {self.user.username})"


class JournalEntry(models.Model):
    """Model for user journal entries"""

    MOOD_CHOICES = [
        ("very_negative", "Very Negative"),
        ("negative", "Negative"),
        ("neutral", "Neutral"),
        ("positive", "Positive"),
        ("very_positive", "Very Positive"),
    ]

    WEATHER_CHOICES = [
        ("sunny", "Sunny"),
        ("cloudy", "Cloudy"),
        ("rainy", "Rainy"),
        ("stormy", "Stormy"),
        ("snowy", "Snowy"),
    ]

    ACTIVITY_CHOICES = [
        ("exercise", "Exercise"),
        ("reading", "Reading"),
        ("meditation", "Meditation"),
        ("socializing", "Socializing"),
        ("working", "Working"),
        ("cooking", "Cooking"),
        ("gardening", "Gardening"),
        ("dancing", "Dancing"),
        ("gaming", "Gaming"),
        ("traveling", "Traveling"),
        ("shopping", "Shopping"),
        ("listening_to_music", "Listening to Music"),
        ("watching_tv", "Watching TV"),
        ("yoga", "Yoga"),
        ("walking", "Walking"),
        ("running", "Running"),
        ("painting", "Painting"),
        ("writing", "Writing"),
        ("cleaning", "Cleaning"),
        ("photography", "Photography"),
    ]

    # Make title optional
    title = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date = models.DateField(default=timezone.now)
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_entries",
    )
    category = models.ForeignKey(
        JournalCategory,
        on_delete=models.SET_NULL,  # If category is deleted, entries remain
        related_name="entries",
        null=True,
        blank=True,
    )
    is_private = models.BooleanField(default=True)
    shared_with_therapist = models.BooleanField(default=False)
    weather = models.CharField(
        max_length=20, choices=WEATHER_CHOICES, null=True, blank=True
    )
    activities = models.CharField(
        max_length=20, choices=ACTIVITY_CHOICES, null=True, blank=True
    )

    class Meta:
        verbose_name_plural = "Journal Entries"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["mood"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.date}"

    def clean(self):
        """Validate the journal entry"""
        pass

    def save(self, *args, **kwargs):
        """Save the journal entry after validation"""
        self.full_clean()
        super().save(*args, **kwargs)
