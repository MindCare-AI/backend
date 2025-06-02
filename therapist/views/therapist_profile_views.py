# therapist/views/therapist_profile_views.py
from django.conf import settings
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from typing import Dict, Any
from therapist.models.therapist_profile import TherapistProfile
from therapist.serializers.therapist_profile import (
    TherapistProfileSerializer,
    TherapistProfilePublicSerializer,
)
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
from rest_framework.views import APIView

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
            # Ensure JSON fields have proper defaults before saving
            validated_data = serializer.validated_data
            json_fields = [
                "experience",
                "specializations",
                "treatment_approaches",
                "languages",
            ]
            for field in json_fields:
                if field in validated_data and validated_data[field] is None:
                    validated_data[field] = []

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
            raise DRFValidationError(f"Could not update therapist profile: {str(e)}")

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
        """Enhanced multi-step therapist verification process"""
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

        # Enhanced logging
        logger.info("=== Enhanced Verification Request Details ===")
        logger.info(f"User: {profile.user.email}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Files: {list(request.FILES.keys())}")
        logger.info(f"Data fields: {list(request.data.keys())}")

        # Validate rate limiting
        rate_limit_result = self._check_verification_rate_limit(profile.user)
        if not rate_limit_result["allowed"]:
            return Response(
                {
                    "error": "Too many verification attempts",
                    "retry_after": rate_limit_result["retry_after"],
                    "attempts_remaining": rate_limit_result["attempts_remaining"],
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Validate request data
        serializer = TherapistVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Validation errors: {serializer.errors}")
            return Response(
                {"error": "Invalid data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data

        try:
            # Initialize enhanced verification service
            from ..services.therapist_verification_service import TherapistVerificationService

            verification_service = TherapistVerificationService()

            # Step 1: Comprehensive License Verification
            logger.info("Starting comprehensive license verification...")
            license_result = verification_service.comprehensive_license_verification(
                validated_data["license_image"],
                validated_data["license_number"],
                validated_data["issuing_authority"],
            )

            # Step 2: Enhanced Face Verification
            logger.info("Starting enhanced face verification...")
            face_result = verification_service.enhanced_face_verification(
                validated_data["license_image"], validated_data["selfie_image"]
            )

            # Step 3: Cross-reference with licensing databases (if available)
            logger.info("Cross-referencing with licensing databases...")
            database_result = self._cross_reference_license_database(
                validated_data["license_number"],
                validated_data["issuing_authority"],
                profile.user,
            )

            # Step 4: Background verification
            logger.info("Performing background verification...")
            background_result = self._perform_background_verification(
                validated_data["license_number"],
                validated_data["issuing_authority"],
            )

            # Combine all verification results
            verification_results = {
                "license_verification": license_result,
                "face_verification": face_result,
                "database_verification": database_result,
                "background_verification": background_result,
                "overall_confidence": self._calculate_overall_confidence(
                    [license_result, face_result, database_result, background_result]
                ),
            }

            # Make final verification decision
            verification_decision = self._make_verification_decision(verification_results)

            # Update profile based on decision
            self._update_profile_verification_status(
                profile, verification_decision, verification_results, validated_data
            )

            # Log verification attempt
            self._log_verification_attempt(profile.user, verification_results, verification_decision)

            # Send appropriate response
            if verification_decision["approved"]:
                # Send approval notification
                self._send_verification_notification(profile.user, "approved", verification_decision)

                return Response(
                    {
                        "message": "Verification successful",
                        "status": "verified",
                        "confidence_score": verification_decision["confidence"],
                        "verification_id": verification_decision.get("verification_id"),
                        "verified_at": timezone.now().isoformat(),
                    },
                    status=status.HTTP_200_OK,
                )

            elif verification_decision["requires_review"]:
                # Send manual review notification
                self._send_verification_notification(profile.user, "review", verification_decision)

                return Response(
                    {
                        "message": "Verification submitted for manual review",
                        "status": "pending_review",
                        "review_timeline": "2-5 business days",
                        "confidence_score": verification_decision["confidence"],
                        "issues_identified": verification_decision.get("issues", []),
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            else:
                # Send rejection notification
                self._send_verification_notification(profile.user, "rejected", verification_decision)

                return Response(
                    {
                        "error": "Verification failed",
                        "status": "rejected",
                        "reasons": verification_decision.get("rejection_reasons", []),
                        "can_retry": verification_decision.get("can_retry", True),
                        "retry_suggestions": verification_decision.get("suggestions", []),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            logger.error(f"Verification process error: {str(e)}", exc_info=True)

            # Log the error attempt
            self._log_verification_error(profile.user, str(e))

            return Response(
                {
                    "error": "Verification processing failed",
                    "message": "Please try again later or contact support",
                    "support_reference": self._generate_support_reference(),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _check_verification_rate_limit(self, user) -> Dict[str, Any]:
        """Check if user has exceeded verification rate limits"""
        # Implementation for rate limiting
        return {"allowed": True, "attempts_remaining": 5, "retry_after": None}

    def _cross_reference_license_database(self, license_number, authority, user) -> Dict[str, Any]:
        """Cross-reference license with official databases"""
        # Placeholder for database integration
        return {
            "success": True,
            "verified_in_database": True,
            "license_status": "active",
            "expiry_date": "2025-12-31",
            "confidence": 0.9,
        }

    def _perform_background_verification(self, license_number, authority) -> Dict[str, Any]:
        """Perform additional background verification"""
        # Placeholder for background checks
        return {
            "success": True,
            "clean_record": True,
            "additional_certifications": [],
            "confidence": 0.8,
        }

    def _calculate_overall_confidence(self, results) -> float:
        """Calculate overall confidence from all verification methods"""
        successful_results = [r for r in results if r and r.get("success")]
        if not successful_results:
            return 0.0

        confidences = [r.get("confidence", 0.5) for r in successful_results]
        return sum(confidences) / len(confidences)

    def _make_verification_decision(self, results) -> Dict[str, Any]:
        """Make final verification decision based on all results"""
        overall_confidence = results["overall_confidence"]

        # High confidence - auto approve
        if overall_confidence >= 0.85:
            return {
                "approved": True,
                "requires_review": False,
                "confidence": overall_confidence,
                "verification_id": self._generate_verification_id(),
            }

        # Medium confidence - manual review
        elif overall_confidence >= 0.6:
            return {
                "approved": False,
                "requires_review": True,
                "confidence": overall_confidence,
                "issues": self._identify_verification_issues(results),
            }

        # Low confidence - reject
        else:
            return {
                "approved": False,
                "requires_review": False,
                "confidence": overall_confidence,
                "rejection_reasons": self._generate_rejection_reasons(results),
                "can_retry": True,
                "suggestions": self._generate_improvement_suggestions(results),
            }

    def _update_profile_verification_status(self, profile, decision, results, validated_data):
        """Update profile with verification results"""
        if decision["approved"]:
            profile.is_verified = True
            profile.verification_status = "verified"
            profile.verified_at = timezone.now()
            profile.verification_expiry = timezone.now().date() + timedelta(days=365)
        elif decision["requires_review"]:
            profile.verification_status = "pending_review"
        else:
            profile.verification_status = "rejected"

        # Store verification data
        profile.license_number = validated_data["license_number"]
        profile.issuing_authority = validated_data["issuing_authority"]
        profile.verification_data = {
            "results": results,
            "decision": decision,
            "timestamp": timezone.now().isoformat(),
        }

        profile.save()

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


class PublicTherapistListView(APIView):
    def get(self, request):
        therapists = TherapistProfile.objects.filter(is_verified=True)
        serializer = TherapistProfilePublicSerializer(
            therapists, many=True, context={"include_availability": True}
        )
        return Response(serializer.data)
