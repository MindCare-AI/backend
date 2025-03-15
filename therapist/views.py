# therapist/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import (
    TherapistProfile,
    Appointment,
    SessionNote,
    ClientFeedback,
)  # Ensure SessionNote and ClientFeedback are defined in therapist/models.py
from .serializers import (
    TherapistProfileSerializer,
    AppointmentSerializer,
    SessionNoteSerializer,
    ClientFeedbackSerializer,
)
from users.permissions import IsSuperUserOrSelf
import logging
from rest_framework.exceptions import ValidationError
import json
from .services import TherapistVerificationService
from django.db import transaction

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(description="List therapist profiles", tags=["Therapist"]),
    retrieve=extend_schema(description="Get therapist profile", tags=["Therapist"]),
    update=extend_schema(description="Update therapist profile", tags=["Therapist"]),
    partial_update=extend_schema(
        description="Patch therapist profile", tags=["Therapist"]
    ),
)
class TherapistProfileViewSet(viewsets.ModelViewSet):
    serializer_class = TherapistProfileSerializer
    permission_classes = [IsSuperUserOrSelf]

    def get_queryset(self):
        """Filter queryset based on user role and query params."""
        user = self.request.user
        base_queryset = TherapistProfile.objects.select_related("user")

        if user.is_superuser:
            return base_queryset.all()

        if user.is_authenticated and user.user_type == "therapist":
            return base_queryset.filter(user=user)

        queryset = base_queryset.filter(user__is_active=True, is_verified=True)
        return self._apply_filters(queryset)

    def _apply_filters(self, queryset):
        """Apply filters from query parameters."""
        params = self.request.query_params

        if specialization := params.get("specialization"):
            queryset = queryset.filter(specialization__icontains=specialization)

        if languages := params.get("languages"):
            queryset = queryset.filter(languages_spoken__contains=languages.split(","))

        if day := params.get("available_day"):
            queryset = queryset.filter(available_days__has_key=day.lower())

        return queryset

    @extend_schema(
        description="Check therapist availability details",
        summary="Check Therapist Availability",
        tags=["Appointments"],
    )
    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        """Custom endpoint to check therapist availability."""
        try:
            therapist = self.get_object()
            return Response(
                {
                    "available_days": therapist.available_days,
                    "video_session_link": therapist.video_session_link,
                    "languages": therapist.languages_spoken,
                }
            )
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not fetch availability"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Book an appointment with the therapist",
        summary="Book Appointment",
        tags=["Appointments"],
    )
    @action(detail=True, methods=["post"])
    def book_appointment(self, request, pk=None):
        """Book an appointment with the therapist."""
        try:
            therapist_profile = self.get_object()

            if request.user.user_type != "patient":
                return Response(
                    {"error": "Only patients can book appointments"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            appointment_data = {
                "therapist": therapist_profile.user.id,
                "patient": request.user.id,
                "date_time": request.data.get("date_time"),
                "duration": request.data.get("duration", 60),
                "notes": request.data.get("notes", ""),
            }

            serializer = AppointmentSerializer(data=appointment_data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error booking appointment: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not book appointment"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="List all appointments for the therapist",
        summary="List Appointments",
        tags=["Appointments"],
    )
    @action(detail=True, methods=["get"])
    def appointments(self, request, pk=None):
        """List all appointments for the therapist."""
        try:
            therapist_profile = self.get_object()
            appointments = Appointment.objects.filter(
                therapist=therapist_profile.user
            ).order_by("date_time")

            serializer = AppointmentSerializer(appointments, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error fetching appointments: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not fetch appointments"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def update_availability(self, request, pk=None):
        """Update therapist availability schedule."""
        try:
            profile = self.get_object()

            if not (schedule := request.data.get("available_days")):
                return Response(
                    {"error": "available_days is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            profile.available_days = self._validate_schedule(schedule)
            profile.save()

            return Response(
                {
                    "message": "Availability updated successfully",
                    "available_days": profile.available_days,
                }
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating availability: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update availability"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate_schedule(self, schedule):
        """Validate availability schedule format."""
        if isinstance(schedule, str):
            try:
                schedule = json.loads(schedule)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format")

        if not isinstance(schedule, dict):
            raise ValidationError("Schedule must be a dictionary")

        valid_days = {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }

        for day, slots in schedule.items():
            if day.lower() not in valid_days:
                raise ValidationError(f"Invalid day: {day}")

            if not isinstance(slots, list):
                raise ValidationError(f"Schedule for {day} must be a list")

            for slot in slots:
                if (
                    not isinstance(slot, dict)
                    or "start" not in slot
                    or "end" not in slot
                ):
                    raise ValidationError(f"Invalid time slot in {day}")

        return schedule

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Handle therapist license verification."""
        try:
            profile = self.get_object()

            if not (docs := request.FILES.get("verification_documents")):
                return Response(
                    {"error": "Verification documents required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                profile.verification_documents = docs
                profile.save()

                verification_service = TherapistVerificationService()
                result = verification_service.verify_license(
                    profile.verification_documents.path
                )

                if result["success"]:
                    return Response(
                        {
                            "message": "Verification successful",
                            "status": profile.verification_status,
                        }
                    )

                return Response(
                    {
                        "error": result.get("error", "Verification failed"),
                        "status": profile.verification_status,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            logger.error(f"Verification failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Verification process failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    list=extend_schema(description="List user's appointments", tags=["Appointments"]),
    retrieve=extend_schema(
        description="Get appointment details", tags=["Appointments"]
    ),
    update=extend_schema(description="Update appointment", tags=["Appointments"]),
    partial_update=extend_schema(
        description="Patch appointment", tags=["Appointments"]
    ),
)
class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = [
        "get",
        "patch",
        "put",
        "delete",
    ]  # No POST - use book_appointment instead

    def get_queryset(self):
        user = self.request.user
        if user.user_type == "therapist":
            return Appointment.objects.filter(therapist=user)
        elif user.user_type == "patient":
            return Appointment.objects.filter(patient=user)
        return Appointment.objects.none()

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirm an appointment."""
        appointment = self.get_object()

        if appointment.therapist != request.user:
            return Response(
                {"error": "Only the therapist can confirm appointments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        appointment.status = "confirmed"
        appointment.save()
        serializer = self.get_serializer(appointment)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel an appointment."""
        appointment = self.get_object()

        if (
            appointment.therapist != request.user
            and appointment.patient != request.user
        ):
            return Response(
                {"error": "Only the therapist or patient can cancel appointments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        appointment.status = "cancelled"
        appointment.save()
        serializer = self.get_serializer(appointment)
        return Response(serializer.data)


class SessionNoteViewSet(viewsets.ModelViewSet):
    queryset = SessionNote.objects.all()
    serializer_class = SessionNoteSerializer


class ClientFeedbackViewSet(viewsets.ModelViewSet):
    queryset = ClientFeedback.objects.all()
    serializer_class = ClientFeedbackSerializer
