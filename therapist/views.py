# therapist/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)  # Import for enhancing Swagger docs
from .models import TherapistProfile, SessionNote, ClientFeedback
from .serializers import (
    TherapistProfileSerializer,
    SessionNoteSerializer,
    ClientFeedbackSerializer,
)
from users.permissions import IsSuperUserOrSelf
import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="Retrieve therapist profiles with filtering options based on years of experience, specialization, availability, and languages spoken.",
        summary="List Therapist Profiles",
        tags=["Therapist Profile"],
    ),
    retrieve=extend_schema(
        description="Retrieve a specific therapist profile's details.",
        summary="Retrieve Therapist Profile",
        tags=["Therapist Profile"],
    ),
    update=extend_schema(
        description="Update a therapist profile.",
        summary="Update Therapist Profile",
        tags=["Therapist Profile"],
    ),
    partial_update=extend_schema(
        description="Partially update a therapist profile.",
        summary="Patch Therapist Profile",
        tags=["Therapist Profile"],
    ),
    destroy=extend_schema(
        description="Delete a therapist profile.",
        summary="Delete Therapist Profile",
        tags=["Therapist Profile"],
    ),
)
class TherapistProfileViewSet(viewsets.ModelViewSet):
    serializer_class = TherapistProfileSerializer
    http_method_names = ["get", "put", "patch", "delete"]  # Remove POST
    permission_classes = [IsSuperUserOrSelf]

    def get_queryset(self):
        """
        Enhanced queryset with filtering capabilities for:
        - Years of experience
        - Specialization
        - Availability
        - Languages spoken
        """
        queryset = TherapistProfile.objects.select_related("user")

        # Filter parameters
        min_experience = self.request.query_params.get("min_experience")
        specialization = self.request.query_params.get("specialization")
        language = self.request.query_params.get("language")
        max_fee = self.request.query_params.get("max_fee")

        # Apply filters
        if min_experience:
            queryset = queryset.filter(years_of_experience__gte=min_experience)

        if specialization:
            queryset = queryset.filter(specialization__icontains=specialization)

        if language:
            queryset = queryset.filter(languages_spoken__contains=[language])

        if max_fee:
            queryset = queryset.filter(consultation_fee__lte=max_fee)

        # User-based filtering
        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)

        return queryset

    @extend_schema(
        description="Custom endpoint to check therapist availability details including available days, consultation fee, video session link, and languages spoken.",
        summary="Check Therapist Availability",
        tags=["Therapist Profile"],
    )
    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        """
        Custom endpoint to check therapist availability.
        """
        try:
            therapist = self.get_object()
            return Response(
                {
                    "available_days": therapist.available_days,
                    "consultation_fee": therapist.consultation_fee,
                    "video_session_link": therapist.video_session_link,
                    "languages": therapist.languages_spoken,
                }
            )
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return Response(
                {"error": "Could not fetch availability"},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema_view(
    list=extend_schema(
        description="Retrieve session notes for the authenticated therapist.",
        summary="List Session Notes",
        tags=["Session Notes"],
    ),
    retrieve=extend_schema(
        description="Retrieve a specific session note.",
        summary="Retrieve Session Note",
        tags=["Session Notes"],
    ),
)
class SessionNoteViewSet(viewsets.ModelViewSet):
    serializer_class = SessionNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SessionNote.objects.filter(therapist=self.request.user)


@extend_schema_view(
    list=extend_schema(
        description="Retrieve client feedback for the authenticated therapist.",
        summary="List Client Feedback",
        tags=["Client Feedback"],
    ),
    retrieve=extend_schema(
        description="Retrieve specific client feedback.",
        summary="Retrieve Client Feedback",
        tags=["Client Feedback"],
    ),
)
class ClientFeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = ClientFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ClientFeedback.objects.filter(therapist=self.request.user)
