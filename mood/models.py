 #mood/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import CustomUser  # Adjusted import

class MoodLog(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="mood_logs"
    )
    mood_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    notes = models.TextField(blank=True)
    logged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-logged_at"]
        indexes = [models.Index(fields=["user", "logged_at"])]

    def __str__(self):
        return f"{self.user.username} - Mood: {self.mood_rating}"
