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
from users.permissions import IsSuperUserOrSelf, IsTherapistForPatient
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
    permission_classes = [IsSuperUserOrSelf]

    def get_queryset(self):
        """
        Return all therapist profiles for admin,
        or just the user's own profile for regular users.
        """
        user = self.request.user
        if user.is_superuser:
            return TherapistProfile.objects.all().select_related('user')
        
        # Filter by some parameter if provided
        specialization = self.request.query_params.get('specialization', None)
        queryset = TherapistProfile.objects.filter(user__user_type='therapist')
        
        if specialization:
            queryset = queryset.filter(specialization__icontains=specialization)
            
        if user.is_authenticated and user.user_type == 'therapist':
            # Just return the user's own profile if they're a therapist
            return TherapistProfile.objects.filter(user=user)
            
        # For patients or anonymous users, return all therapist profiles
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
        except TherapistProfile.DoesNotExist:
            logger.warning(f"Therapist profile not found: {pk}")
            return Response(
                {"error": "Therapist profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not fetch availability. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def update_availability(self, request, pk=None):
        """
        Update therapist availability
        """
        try:
            therapist = self.get_object()
            
            # Check permissions
            if therapist.user != request.user and not request.user.is_superuser:
                return Response(
                    {"error": "You don't have permission to update this therapist's availability"},
                    status=status.HTTP_403_FORBIDDEN
                )
                
            # Update available days
            available_days = request.data.get('available_days')
            if available_days:
                therapist.available_days = available_days
                therapist.save()
                
            return Response({
                "message": "Availability updated successfully",
                "available_days": therapist.available_days,
            })
            
        except Exception as e:
            logger.error(f"Error updating availability: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not update availability. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
