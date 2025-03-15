from django.contrib import admin
from .models import TherapistProfile, Appointment, SessionNote, ClientFeedback
from django.utils.html import format_html


@admin.register(TherapistProfile)
class TherapistProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "specialization",
        "license_number",
        "years_of_experience",
        "verification_status",
        "license_expiry_status",
        "profile_completion_percentage",
    )
    list_filter = (
        "specialization",
        "years_of_experience",
        "license_expiry",
        "verification_status",
        "is_verified",
    )
    search_fields = ("user__username", "specialization", "license_number")
    readonly_fields = (
        "profile_pic_preview",
        "profile_completion_percentage",
        "is_profile_complete",
        "created_at",
        "updated_at",
    )
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
                    "languages_spoken",
                )
            },
        ),
        ("Availability", {"fields": ("available_days", "video_session_link")}),
        (
            "Verification",
            {
                "fields": (
                    "verification_status",
                    "verification_notes",
                    "verification_documents",
                    "is_verified",
                    "last_verification_attempt",
                )
            },
        ),
        (
            "Profile Status",
            {
                "fields": (
                    "profile_completion_percentage",
                    "is_profile_complete",
                    "created_at",
                    "updated_at",
                )
            },
        ),
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


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "therapist",
        "patient",
        "date_time",
        "duration",
        "status",
        "created_at",
    )
    list_filter = ("status", "date_time")
    search_fields = ("therapist__username", "patient__username", "notes")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-date_time",)


@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = ("therapist", "patient", "session_date", "timestamp")
    list_filter = ("session_date", "timestamp")
    search_fields = ("therapist__username", "patient__username", "notes")
    readonly_fields = ("timestamp", "updated_at")


@admin.register(ClientFeedback)
class ClientFeedbackAdmin(admin.ModelAdmin):
    list_display = ("therapist", "patient", "rating", "timestamp")
    list_filter = ("rating", "timestamp")
    search_fields = ("therapist__username", "patient__username", "feedback")
    readonly_fields = ("timestamp",)
