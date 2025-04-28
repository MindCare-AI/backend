# therapist/views/therapist_profile_views.py
from django.conf import settings
from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from appointments.models import Appointment
from therapist.models.therapist_profile import TherapistProfile
from appointments.serializers import AppointmentSerializer
from therapist.serializers.therapist_profile import TherapistProfileSerializer
from therapist.serializers.verification import TherapistVerificationSerializer, VerificationStatusSerializer
from therapist.permissions.therapist_permissions import IsPatient, IsSuperUserOrSelf
import logging
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
import json
from therapist.services.therapist_verification_service import (
    TherapistVerificationService,
)
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.cache import cache
import magic
from rest_framework.parsers import MultiPartParser, FormParser

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
    queryset = TherapistProfile.objects.all()
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return TherapistProfile.objects.select_related("user").all()
        return TherapistProfile.objects.select_related("user").filter(
            user=self.request.user
        )

    def get_serializer_class(self):
        """Return appropriate serializer class based on action"""
        if self.action == 'verify':
            if self.request.method == 'GET':
                return VerificationStatusSerializer
            return TherapistVerificationSerializer
        return TherapistProfileSerializer

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
                serializer.save()
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
        # disallow changing the user FK
        if "user" in self.request.data:
            raise DRFValidationError({"user": "User field cannot be modified"})

        try:
            serializer.save()
        except DjangoValidationError as e:
            # propagate your model.clean() messages verbatim
            raise DRFValidationError(detail=e.messages)
        except DRFValidationError:
            # if serializer.is_valid() already raised, let it through
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating therapist profile: {e}", exc_info=True
            )
            raise DRFValidationError("Could not update therapist profile")

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

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
    @action(detail=True, methods=["post"], permission_classes=[IsPatient])
    def book_appointment(self, request, pk=None, **kwargs):
        """Book an appointment with a therapist."""
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
                "therapist": therapist_profile.id,
                "patient": request.user.patient_profile.id,
                "appointment_date": request.data.get("appointment_date"),
                "duration": timedelta(
                    minutes=int(request.data.get("duration_minutes", 60))
                ),
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
                    f"Time: {appointment.appointment_date}, "
                    f"Duration: {appointment.duration}"
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except TherapistProfile.DoesNotExist:
            return Response(
                {"error": "Therapist profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (DjangoValidationError, DRFValidationError) as e:
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
    def appointments(self, request, pk=None, **kwargs):
        try:
            therapist_profile = self.get_object()
            appointments = Appointment.objects.filter(
                therapist=therapist_profile
            ).order_by("appointment_date")
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
        description="Verify therapist license and identity or check verification status",
        summary="Verify/Check Therapist Status",
        tags=["Therapist"],
        request={
            'multipart/form-data': TherapistVerificationSerializer,
        },
        responses={
            200: VerificationStatusSerializer,
            400: {"description": "Bad request - invalid data"},
            429: {"description": "Too many verification attempts"},
            500: {"description": "Internal server error"},
        }
    )
    @action(
        detail=True,
        methods=['get', 'post'],
        parser_classes=[MultiPartParser, FormParser],
        url_path='verify',
        url_name='verify'
    )
    def verify(self, request, pk=None):
        """Verify therapist's credentials or check verification status"""
        profile = self.get_object()

        # Handle GET request to check verification status
        if request.method == "GET":
            serializer = VerificationStatusSerializer(profile)
            return Response(serializer.data)

        # Handle POST request for verification
        if profile.is_verified:
            return Response(
                {"error": "Profile is already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Log detailed request information
        logger.info("=== Verification Request Details ===")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Files: {request.FILES}")
        logger.info(f"POST data: {request.POST}")
        logger.info(f"Data: {request.data}")

        # Rate limiting check
        cache_key = f"verification_attempts_{profile.id}"
        attempts = cache.get(cache_key, 0)
        max_attempts = settings.VERIFICATION_SETTINGS["MAX_VERIFICATION_ATTEMPTS"]
        cooldown_minutes = settings.VERIFICATION_SETTINGS["VERIFICATION_COOLDOWN_MINUTES"]

        if attempts >= max_attempts:
            return Response(
                {
                    "error": f"Maximum verification attempts ({max_attempts}) reached. Please try again after {cooldown_minutes} minutes.",
                    "next_attempt": cache.ttl(cache_key),
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Check if required files are present
        if 'license_image' not in request.FILES:
            return Response(
                {"error": "License image is required", "field": "license_image"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if 'selfie_image' not in request.FILES:
            return Response(
                {"error": "Selfie image is required", "field": "selfie_image"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if required fields are present
        if not request.POST.get('license_number'):
            return Response(
                {"error": "License number is required", "field": "license_number"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.POST.get('issuing_authority'):
            return Response(
                {"error": "Issuing authority is required", "field": "issuing_authority"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Log the data that will be passed to the serializer
        serializer_data = {
            'license_image': request.FILES.get('license_image'),
            'selfie_image': request.FILES.get('selfie_image'),
            'license_number': request.POST.get('license_number'),
            'issuing_authority': request.POST.get('issuing_authority'),
        }
        logger.info("=== Serializer Input Data ===")
        logger.info(f"Data being passed to serializer: {serializer_data}")

        # Validate request data
        serializer = TherapistVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("=== Serializer Validation Errors ===")
            logger.warning(f"Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification_service = TherapistVerificationService()

            # Verify license
            license_result = verification_service.verify_license(
                serializer.validated_data["license_image"],
                expected_number=serializer.validated_data["license_number"],
                issuing_authority=serializer.validated_data["issuing_authority"],
            )

            if not license_result["success"]:
                cache.set(cache_key, attempts + 1, timeout=cooldown_minutes * 60)  # Convert minutes to seconds
                return Response(
                    {"error": license_result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Verify face match
            face_result = verification_service.verify_face_match(
                serializer.validated_data["license_image"],
                serializer.validated_data["selfie_image"],
                threshold=settings.VERIFICATION_SETTINGS["FACE_VERIFICATION"]["CONFIDENCE_THRESHOLD"]
            )

            if not face_result["success"] or not face_result["match"]:
                cache.set(cache_key, attempts + 1, timeout=cooldown_minutes * 60)
                return Response(
                    {
                        "error": "Face verification failed - ID and selfie don't match",
                        "details": face_result.get("details", {}),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                # Update verification documents and status
                profile.verification_documents = serializer.validated_data["license_image"]
                profile.profile_picture = serializer.validated_data["selfie_image"]
                profile.verification_status = "verified"
                profile.is_verified = True
                profile.verified_at = timezone.now()
                profile.verification_expiry = timezone.now() + timedelta(
                    days=settings.VERIFICATION_SETTINGS["LICENSE_VALIDITY"]["DEFAULT_DURATION_DAYS"]
                )

                # Update professional details
                profile.license_number = serializer.validated_data["license_number"]
                profile.issuing_authority = serializer.validated_data["issuing_authority"]
                if specializations := serializer.validated_data.get("specializations"):
                    profile.specializations = specializations
                profile.verification_notes = "Verification completed successfully"
                profile.save()

                # Clear verification attempts on success
                cache.delete(cache_key)

                # Return success response with verification status
                status_serializer = VerificationStatusSerializer(profile)
                return Response(status_serializer.data)

        except Exception as e:
            logger.error(f"Verification failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Verification process failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PublicTherapistListView(generics.ListAPIView):
    """
    Lists all verified therapist profiles.
    """

    queryset = TherapistProfile.objects.filter(is_verified=True)
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.AllowAny]
