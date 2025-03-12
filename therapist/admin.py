from django.contrib import admin
from .models import TherapistProfile
from django.utils.html import format_html


@admin.register(TherapistProfile)
class TherapistProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "specialization",
        "license_number",
        "years_of_experience",
        "consultation_fee",
        "license_expiry_status",
        "profile_pic_preview",
    )
    list_filter = ("specialization", "years_of_experience", "license_expiry")
    search_fields = ("user__username", "specialization", "license_number")
    readonly_fields = ("profile_pic_preview",)
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "user",
                    "specialization",
                    "bio",
                    "profile_pic",
                    "profile_pic_preview",
                )
            },
        ),
        (
            "Professional Details",
            {
                "fields": (
                    "license_number",
                    "years_of_experience",
                    "treatment_approaches",
                    "consultation_fee",
                )
            },
        ),
        ("Availability", {"fields": ("available_days", "video_session_link")}),
        ("License Information", {"fields": ("license_expiry",)}),
    )

    def license_expiry_status(self, obj):
        if obj.license_expiry:
            from django.utils.timezone import now

            if obj.license_expiry > now().date():
                return format_html('<span style="color: green;">Valid</span>')
            else:
                return format_html('<span style="color: red;">Expired</span>')
        return "N/A"

    license_expiry_status.short_description = "License Status"

    def profile_pic_preview(self, obj):
        if obj.profile_pic:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.profile_pic.url,
            )
        return "No Image"

    profile_pic_preview.short_description = "Profile Picture"
