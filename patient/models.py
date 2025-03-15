# patient/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import CustomUser


class PatientProfile(models.Model):
    BLOOD_TYPE_CHOICES = [
        ("A+", "A Positive"),
        ("A-", "A Negative"),
        ("B+", "B Positive"),
        ("B-", "B Negative"),
        ("AB+", "AB Positive"),
        ("AB-", "AB Negative"),
        ("O+", "O Positive"),
        ("O-", "O Negative"),
    ]

    # Required Fields
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="patient_profile"
    )

    # Add this field with a default value
    profile_type = models.CharField(
        max_length=10,
        choices=[("patient", "Patient"), ("therapist", "Therapist")],
        default="patient",
    )

    # Optional Medical Information
    medical_history = models.TextField(blank=True, null=True)
    current_medications = models.TextField(blank=True, null=True)
    blood_type = models.CharField(
        max_length=3, choices=BLOOD_TYPE_CHOICES, blank=True, null=True
    )
    treatment_plan = models.TextField(blank=True, null=True)
    pain_level = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)], blank=True, null=True
    )

    # Optional Profile Info
    profile_pic = models.ImageField(
        upload_to="patient_profile_pics/%Y/%m/", null=True, blank=True
    )

    # Appointment Information
    last_appointment = models.DateTimeField(blank=True, null=True)
    next_appointment = models.DateTimeField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Patient Profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}'s patient profile"

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class MoodLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    mood = models.CharField(
        max_length=20,
        choices=[
            ("happy", "Happy"),
            ("sad", "Sad"),
            ("neutral", "Neutral"),
            ("anxious", "Anxious"),
        ],
    )
    timestamp = models.DateTimeField(auto_now_add=True)
