# mood/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg
from users.models import CustomUser

ACTIVITY_CHOICES = [
    ('Exercise', 'Exercise'),
    ('Meditation', 'Meditation'),
    ('Reading', 'Reading'),
    ('Socializing', 'Socializing'),
    ('Cooking', 'Cooking'),
    ('Working', 'Working'),
    ('Sleeping', 'Sleeping'),
    ('Walking', 'Walking'),
    ('Running', 'Running'),
    ('Yoga', 'Yoga'),
    ('Dancing', 'Dancing'),
    ('Gaming', 'Gaming'),
    ('Traveling', 'Traveling'),
    ('Shopping', 'Shopping'),
    ('Listening to Music', 'Listening to Music'),
    ('Watching TV', 'Watching TV'),
    ('Gardening', 'Gardening'),
    ('Art', 'Art'),
    ('Writing', 'Writing'),
    ('Cleaning', 'Cleaning'),
]

class MoodLog(models.Model):
    ENERGY_CHOICES = [
        (1, 'Very Low'),
        (2, 'Low'),
        (3, 'Moderate'),
        (4, 'High'),
        (5, 'Very High')
    ]
    
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="mood_logs"
    )
    mood_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    energy_level = models.IntegerField(
        choices=ENERGY_CHOICES,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    activities = models.CharField(
        max_length=50,
        choices=ACTIVITY_CHOICES,
        blank=True,
        null=True,
        help_text="Select one activity from a fixed list"
    )
    logged_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    journal_entry = models.OneToOneField(
        'journal.JournalEntry', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='mood_log'
    )

    class Meta:
        ordering = ["-logged_at"]
        indexes = [models.Index(fields=["user", "logged_at"])]

    def __str__(self):
        return f"{self.user.username} - Mood: {self.mood_rating}"
    
    @classmethod
    def get_average_mood(cls, user, days=7):
        """Get user's average mood over specified days"""
        time_threshold = timezone.now() - timezone.timedelta(days=days)
        avg = cls.objects.filter(
            user=user,
            logged_at__gte=time_threshold
        ).aggregate(avg_mood=Avg('mood_rating'))
        return avg['avg_mood'] or 0
    
    @classmethod
    def get_mood_trend(cls, user, days=30):
        """Get user's mood trend data over specified days"""
        time_threshold = timezone.now() - timezone.timedelta(days=30)
        mood_logs = cls.objects.filter(
            user=user,
            logged_at__gte=time_threshold
        ).order_by('logged_at').values('logged_at', 'mood_rating')
        
        return list(mood_logs)
        
    def create_journal_from_mood(self):
        """Create a journal entry based on this mood log"""
        if hasattr(self, 'journal_entry') and self.journal_entry:
            return self.journal_entry
            
        from journal.models import JournalEntry
        
        title = f"Mood Entry: {self.get_mood_description()}"
        content = f"I logged my mood as {self.mood_rating}/10."
        
        if self.activities:
            content += f"\n\nActivity: {self.activities}"
        
        journal_entry = JournalEntry.objects.create(
            user=self.user,
            title=title,
            content=content,
            mood_rating=self.mood_rating
        )
        
        self.journal_entry = journal_entry
        self.save()
        
        return journal_entry
    
    def get_mood_description(self):
        """Get descriptive text for mood rating"""
        if self.mood_rating <= 2:
            return "Very Low"
        elif self.mood_rating <= 4:
            return "Low"
        elif self.mood_rating <= 6:
            return "Moderate"
        elif self.mood_rating <= 8:
            return "Good"
        else:
            return "Excellent"
