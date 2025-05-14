# therapist/views/therapist_profile_views.py
from django.conf import settings
from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from therapist.models.therapist_profile import TherapistProfile
from therapist.serializers.therapist_profile import TherapistProfileSerializer
from therapist.serializers.verification import (
    TherapistVerificationSerializer,
    VerificationStatusSerializer,
)
from therapist.serializers.availability import TherapistAvailabilitySerializer
from therapist.permissions.therapist_permissions import (
    IsSuperUserOrSelf,
    IsVerifiedTherapist,
)
import logging
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from therapist.services.therapist_verification_service import (
    TherapistVerificationService,
)
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import ValidationError
from rest_framework.permissions import AllowAny

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
    permission_classes = [
        permissions.IsAuthenticated,
        IsSuperUserOrSelf,
        IsVerifiedTherapist,
    ]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return TherapistProfile.objects.select_related("user").all()
        return TherapistProfile.objects.select_related("user").filter(
            user=self.request.user
        )

    def get_serializer_class(self):
        """Return appropriate serializer class based on action"""
        if self.action == "verify":
            if self.request.method == "GET":
                return VerificationStatusSerializer
            return TherapistVerificationSerializer
        elif self.action in ["availability", "update_availability"]:
            return TherapistAvailabilitySerializer
        return TherapistProfileSerializer

    def get_permissions(self):
        if self.action == "verify":
            return [AllowAny()]
        return super().get_permissions()

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
        description="Get or update therapist availability details",
        summary="Therapist Availability",
        tags=["Therapist"],
    )
    @action(detail=True, methods=["get", "post", "patch"], url_path="availability")
    def availability(self, request, pk=None):
        therapist = self.get_object()  # permission checks etc.

        if request.method == "GET":
            # Format for display in the browsable API
            serializer = TherapistAvailabilitySerializer(therapist)
            return Response(serializer.data)
        else:  # POST or PATCH
            serializer = TherapistAvailabilitySerializer(
                therapist, data=request.data, partial=(request.method == "PATCH")
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

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
            if not request.data.get("available_days"):
                return Response(
                    {"error": "available_days is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Validate schedule with serializer
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(
                {
                    "message": "Availability updated successfully",
                    "availability": serializer.data,
                }
            )
        except (ValidationError, DRFValidationError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating availability: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update availability"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Verify therapist license and identity or check verification status",
        summary="Verify/Check Therapist Status",
        tags=["Therapist"],
        request={
            "multipart/form-data": TherapistVerificationSerializer,
        },
        responses={
            200: VerificationStatusSerializer,
            400: {"description": "Bad request - invalid data"},
            429: {"description": "Too many verification attempts"},
            500: {"description": "Internal server error"},
        },
    )
    @action(
        detail=True,
        methods=["get", "post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="verify",
        url_name="verify",
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
        cooldown_minutes = settings.VERIFICATION_SETTINGS[
            "VERIFICATION_COOLDOWN_MINUTES"
        ]

        if attempts >= max_attempts:
            return Response(
                {
                    "error": f"Maximum verification attempts ({max_attempts}) reached. Please try again after {cooldown_minutes} minutes.",
                    "next_attempt": cache.ttl(cache_key),
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Check if required files are present
        if "license_image" not in request.FILES:
            return Response(
                {"error": "License image is required", "field": "license_image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "selfie_image" not in request.FILES:
            return Response(
                {"error": "Selfie image is required", "field": "selfie_image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if required fields are present
        if not request.POST.get("license_number"):
            return Response(
                {"error": "License number is required", "field": "license_number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.POST.get("issuing_authority"):
            return Response(
                {
                    "error": "Issuing authority is required",
                    "field": "issuing_authority",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Log the data that will be passed to the serializer
        serializer_data = {
            "license_image": request.FILES.get("license_image"),
            "selfie_image": request.FILES.get("selfie_image"),
            "license_number": request.POST.get("license_number"),
            "issuing_authority": request.POST.get("issuing_authority"),
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
                cache.set(
                    cache_key, attempts + 1, timeout=cooldown_minutes * 60
                )  # Convert minutes to seconds
                return Response(
                    {"error": license_result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Verify face match
            face_result = verification_service.verify_face_match(
                serializer.validated_data["license_image"],
                serializer.validated_data["selfie_image"],
                threshold=settings.VERIFICATION_SETTINGS["FACE_VERIFICATION"][
                    "CONFIDENCE_THRESHOLD"
                ],
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
                profile.verification_documents = serializer.validated_data[
                    "license_image"
                ]
                profile.profile_picture = serializer.validated_data["selfie_image"]
                profile.verification_status = "verified"
                profile.is_verified = True
                profile.verified_at = timezone.now()
                profile.verification_expiry = timezone.now() + timedelta(
                    days=settings.VERIFICATION_SETTINGS["LICENSE_VALIDITY"][
                        "DEFAULT_DURATION_DAYS"
                    ]
                )

                # Update professional details
                profile.license_number = serializer.validated_data["license_number"]
                profile.issuing_authority = serializer.validated_data[
                    "issuing_authority"
                ]
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

    @extend_schema(
        description="Get therapist's appointments",
        summary="Get Appointments",
        tags=["Therapist"],
    )
    @action(detail=True, methods=["get"])
    def appointments(self, request, pk=None):
        """List all appointments for the therapist - redirects to appointments app"""
        from appointments.models import Appointment
        from appointments.serializers import AppointmentSerializer

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


class PublicTherapistListView(generics.ListAPIView):
    """
    Lists all verified therapist profiles.
    """

    queryset = TherapistProfile.objects.filter(is_verified=True)
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.AllowAny]
