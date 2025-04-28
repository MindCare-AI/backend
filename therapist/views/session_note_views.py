# therapist/views/session_note_views.py
from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils import timezone
from django.db import transaction
import logging
from therapist.models.session_note import SessionNote
from therapist.serializers.session_note import SessionNoteSerializer
from therapist.permissions.therapist_permissions import IsTherapistOrReadOnly

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List session notes",
        summary="List Session Notes",
        tags=["Session Notes"],
    ),
    create=extend_schema(
        description="Create a new session note",
        summary="Create Session Note",
        tags=["Session Notes"],
    ),
    retrieve=extend_schema(
        description="Get a specific session note",
        summary="Get Session Note",
        tags=["Session Notes"],
    ),
    update=extend_schema(
        description="Update a session note",
        summary="Update Session Note",
        tags=["Session Notes"],
    ),
    partial_update=extend_schema(
        description="Partially update a session note",
        summary="Patch Session Note",
        tags=["Session Notes"],
    ),
    destroy=extend_schema(
        description="Delete a session note",
        summary="Delete Session Note",
        tags=["Session Notes"],
    ),
)
class SessionNoteViewSet(viewsets.ModelViewSet):
    """ViewSet for managing therapy session notes"""
    serializer_class = SessionNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsTherapistOrReadOnly]
    
    def get_queryset(self):
        """Filter session notes based on user role"""
        user = self.request.user
        
        if user.user_type == "therapist":
            # For therapist, show only their notes
            return SessionNote.objects.filter(therapist=user)  # Use user instead of therapist_profile
        elif user.user_type == "patient":
            # For patients, show only notes about them
            return SessionNote.objects.filter(patient=user)  # Use user instead of patient_profile
        elif user.is_staff:
            # For admins, show all notes
            return SessionNote.objects.all()
        
        # Default: return empty queryset
        return SessionNote.objects.none()
    
    def perform_create(self, serializer):
        """Set the therapist when creating a note"""
        try:
            with transaction.atomic():
                serializer.save(
                    therapist=self.request.user,  # Use user instead of therapist_profile
                    session_date=serializer.validated_data.get('session_date') or timezone.now().date()
                )
        except Exception as e:
            logger.error(f"Error creating session note: {str(e)}", exc_info=True)
            raise

    def perform_update(self, serializer):
        """Update a session note"""
        try:
            with transaction.atomic():
                # Ensure only the therapist who created the note can update it
                instance = self.get_object()
                if instance.therapist != self.request.user:  # Compare directly with request.user
                    raise permissions.PermissionDenied(
                        "You can only update your own session notes"
                    )
                serializer.save()
        except Exception as e:
            logger.error(f"Error updating session note: {str(e)}", exc_info=True)
            raise
            
    def perform_destroy(self, instance):
        """Delete a session note"""
        try:
            # Ensure only the therapist who created the note can delete it
            if instance.therapist != self.request.user:  # Compare directly with request.user
                raise permissions.PermissionDenied(
                    "You can only delete your own session notes"
                )
            instance.delete()
        except Exception as e:
            logger.error(f"Error deleting session note: {str(e)}", exc_info=True)
            raise
