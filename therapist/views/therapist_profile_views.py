# therapist/views/therapist_profile_views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from therapist.models.appointment import Appointment
from therapist.models.therapist_profile import TherapistProfile
from therapist.serializers.appointment import AppointmentSerializer
from therapist.serializers.therapist_profile import TherapistProfileSerializer
from therapist.permissions.therapist_permissions import IsPatient
from therapist.permissions.therapist_permissions import IsSuperUserOrSelf
import logging
from rest_framework.exceptions import ValidationError
import json
from therapist.services.therapist_verification_service import (
    TherapistVerificationService,
)
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="Get therapist profile information",
        summary="Get Therapist Profile",
        tags=["Therapist Profile"],
    ),
    update=extend_schema(
        description="Update therapist profile information",
        summary="Update Therapist Profile",
        tags=["Therapist Profile"],
    ),
)
class TherapistProfileViewSet(viewsets.ModelViewSet):
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
    http_method_names = ["get", "put", "patch", "delete"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return TherapistProfile.objects.select_related("user").all()
        return TherapistProfile.objects.select_related("user").filter(
            user=self.request.user
        )

    def create(self, request, *args, **kwargs):
        try:
            if not request.user.user_type == "therapist":
                return Response(
                    {"error": "Only therapists can create profiles"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if TherapistProfile.objects.filter(user=request.user).exists():
                return Response(
                    {"error": "Profile already exists for this user"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = request.data.copy()
            data["user"] = request.user.id

            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)

            with transaction.atomic():
                profile = serializer.save()
                logger.info(
                    f"Created therapist profile for user {request.user.username}"
                )

                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating therapist profile: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not create therapist profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def perform_update(self, serializer):
        try:
            if "user" in self.request.data:
                raise ValidationError("User field cannot be modified")

            serializer.save()
            logger.info(
                f"Updated therapist profile for user {self.request.user.username}"
            )

        except Exception as e:
            logger.error(f"Error updating therapist profile: {str(e)}", exc_info=True)
            raise ValidationError("Could not update therapist profile")

    @extend_schema(
        description="Check therapist availability details",
        summary="Check Therapist Availability",
        tags=["Appointments"],
    )
    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
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
        description="Book an appointment with a therapist",
        summary="Book Appointment",
        tags=["Appointments"],
        request=AppointmentSerializer,
        responses={
            201: AppointmentSerializer,
            400: {"description": "Bad request - invalid data"},
            403: {"description": "Forbidden - not authorized"},
            404: {"description": "Not found - therapist profile does not exist"},
        },
    )
    @action(detail=True, methods=["get", "post"], permission_classes=[IsPatient])
    def book_appointment(self, request, pk=None):
        if request.method == "GET":
            return Response(
                {
                    "example_request": {
                        "date_time": "2024-01-01T10:00:00Z",
                        "duration": 60,
                        "notes": "Initial consultation",
                    }
                },
                status=status.HTTP_200_OK,
            )

        try:
            therapist_profile = self.get_object()

            if not therapist_profile.is_verified:
                return Response(
                    {"error": "Therapist's profile is not verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if request.user == therapist_profile.user:
                return Response(
                    {"error": "You cannot book an appointment with yourself"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            appointment_data = {
                "therapist": therapist_profile.id,  # ✅ Use TherapistProfile ID
                "patient": request.user.patient_profile.id,  # ✅ Use PatientProfile ID
                "date_time": request.data.get("date_time"),
                "duration": request.data.get("duration", 60),
                "notes": request.data.get("notes", ""),
                "status": "scheduled",
            }

            serializer = AppointmentSerializer(data=appointment_data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                appointment = serializer.save()
                logger.info(
                    f"Appointment booked - Therapist: {therapist_profile.user.username}, "
                    f"Patient: {request.user.username}, "
                    f"Time: {appointment.date_time}, "
                    f"Duration: {appointment.duration}min"
                )

                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except TherapistProfile.DoesNotExist:
            return Response(
                {"error": "Therapist profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
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
        responses={
            200: AppointmentSerializer(many=True),
            500: {"description": "Internal server error"},
        },
    )
    @action(detail=True, methods=["get"])
    def appointments(self, request, pk=None):
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

    @extend_schema(
        description="Update therapist availability schedule",
        summary="Update Availability",
        tags=["Therapist"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "available_days": {
                        "type": "object",
                        "example": {"monday": [{"start": "09:00", "end": "17:00"}]},
                    }
                },
            }
        },
        responses={
            200: {
                "description": "Availability updated successfully",
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "available_days": {"type": "object"},
                },
            },
            400: {"description": "Invalid schedule format"},
        },
    )
    @action(detail=True, methods=["post"])
    def update_availability(self, request, pk=None):
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

    @extend_schema(
        description="Verify therapist license and credentials",
        summary="Verify Therapist",
        tags=["Therapist"],
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "verification_documents": {"type": "string", "format": "binary"}
                },
                "required": ["verification_documents"],
            }
        },
        responses={
            200: {
                "description": "Verification successful",
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "status": {"type": "string"},
                    "license_details": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "string"},
                            "expiry": {"type": "string", "format": "date"},
                        },
                    },
                },
            },
            400: {"description": "Verification failed"},
            500: {"description": "Internal server error"},
        },
    )
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        try:
            profile = self.get_object()

            if not (docs := request.FILES.get("verification_documents")):
                return Response(
                    {"error": "Verification documents required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                profile.verification_documents = docs
                profile.last_verification_attempt = timezone.now()

                verification_service = TherapistVerificationService()
                result = verification_service.verify_license(
                    profile.verification_documents.path
                )

                if result["success"]:
                    profile.verification_status = "verified"
                    profile.is_verified = True

                    if license_number := result.get("license_number"):
                        profile.license_number = license_number
                    if license_expiry := result.get("license_expiry"):
                        profile.license_expiry = license_expiry

                    profile.verification_notes = "Verification completed successfully"
                    profile.save()

                    return Response(
                        {
                            "message": "Verification successful",
                            "status": profile.verification_status,
                            "license_details": {
                                "number": profile.license_number,
                                "expiry": profile.license_expiry,
                            },
                        }
                    )

                profile.verification_status = "rejected"
                profile.verification_notes = result.get("error", "Verification failed")
                profile.save()

                return Response(
                    {
                        "error": profile.verification_notes,
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
