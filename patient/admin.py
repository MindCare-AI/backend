from django.contrib import admin
from .models import PatientProfile
from django.utils.html import format_html


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "blood_type",
        "pain_level",
        "last_appointment",
        "next_appointment",
        "emergency_contact_display",
        "profile_pic_preview",
    )
    list_filter = ("blood_type", "pain_level", "last_appointment")
    search_fields = ("user__username", "medical_history", "current_medications")
    readonly_fields = ("profile_pic_preview",)
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("user", "bio", "profile_pic", "profile_pic_preview")},
        ),
        (
            "Medical Details",
            {
                "fields": (
                    "medical_history",
                    "current_medications",
                    "blood_type",
                    "pain_level",
                )
            },
        ),
        ("Appointments", {"fields": ("last_appointment", "next_appointment")}),
        ("Emergency Contact", {"fields": ("emergency_contact",)}),
    )

    def emergency_contact_display(self, obj):
        if obj.emergency_contact:
            return f"{obj.emergency_contact.get('name')} ({obj.emergency_contact.get('relationship')})"
        return "N/A"

    emergency_contact_display.short_description = "Emergency Contact"

    def profile_pic_preview(self, obj):
        if obj.profile_pic:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.profile_pic.url,
            )
        return "No Image"

    profile_pic_preview.short_description = "Profile Picture"
