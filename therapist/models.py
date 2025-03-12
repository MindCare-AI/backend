# therapist/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import (
    RegexValidator,
    MinValueValidator,
    MaxValueValidator,
)
from users.models import CustomUser


class TherapistProfile(models.Model):
    # Basic information - required
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name="therapist_profile_therapist"
    )
    
    # Core professional details - allow them to be optional initially
    specialization = models.CharField(max_length=100, blank=True, default="")
    license_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="License number format: AA-123456"
    )
    years_of_experience = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=0
    )
    
    # Optional profile details
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(
        upload_to="therapist_profile_pics/", 
        null=True, 
        blank=True
    )

    # Professional fields - all optional for registration
    treatment_approaches = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Therapy methods and approaches used"
    )
    consultation_fee = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=0.0, 
        validators=[MinValueValidator(0)]
    )
    available_days = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Weekly availability schedule"
    )
    license_expiry = models.DateField(blank=True, null=True)
    video_session_link = models.URLField(blank=True, null=True)
    languages_spoken = models.JSONField(
        default=list,
        blank=True,
        help_text="Languages the therapist can conduct sessions in"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Profile completion status
    is_profile_complete = models.BooleanField(default=False)
    profile_completion_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        verbose_name_plural = "Therapist Profiles"

    def __str__(self):
        return f"{self.user.username}'s therapist profile"
        
    def save(self, *args, **kwargs):
        # Auto-calculate profile completion percentage
        self._calculate_profile_completion()
        super().save(*args, **kwargs)
        
    def _calculate_profile_completion(self):
        """Calculate profile completion percentage based on filled fields"""
        required_fields = [
            self.specialization,
            self.license_number,
            self.bio, 
            self.profile_pic,
            self.treatment_approaches,
            self.available_days,
        ]
        
        filled_count = sum(1 for field in required_fields if field)
        self.profile_completion_percentage = int((filled_count / len(required_fields)) * 100)
        self.is_profile_complete = self.profile_completion_percentage == 100


class SessionNote(models.Model):
    therapist = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="session_notes"
    )
    patient = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="patient_notes"
    )
    notes = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)


class ClientFeedback(models.Model):
    therapist = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="feedback_received"
    )
    patient = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="feedback_given"
    )
    feedback = models.TextField()
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    timestamp = models.DateTimeField(auto_now_add=True)
