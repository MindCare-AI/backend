# patient/models/patient_profile.py
from django.db import models
from django.utils import timezone
from users.models import CustomUser
from users.models.profile import Profile


class PatientProfile(Profile):
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

    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
        ("N", "Prefer not to say"),
    ]

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="patient_profile"
    )

    emergency_contact = models.JSONField(default=dict, blank=True, null=True)
    blood_type = models.CharField(
        max_length=3, choices=BLOOD_TYPE_CHOICES, blank=True, null=True
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        null=True,
        help_text="Patient's gender identification",
    )

    profile_pic = models.ImageField(
        upload_to="patient_profile_pics/%Y/%m/", null=True, blank=True
    )

    created_at = models.DateTimeField(editable=False, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        verbose_name = "Patient Profile"
        verbose_name_plural = "Patient Profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}'s Patient Profile"

    def save(self, *args, **kwargs):
        if not self.pk:  # Object is being created
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
