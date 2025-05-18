# patient/views/client_feedback_views.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
import logging
from django.db import transaction
from patient.models.client_feedback import ClientFeedback
from patient.serializers.client_feedback import ClientFeedbackSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List client feedback",
        summary="List Client Feedback",
        tags=["Client Feedback"],
    ),
    create=extend_schema(
        description="Submit new feedback",
        summary="Submit Feedback",
        tags=["Client Feedback"],
    ),
    retrieve=extend_schema(
        description="Get specific feedback",
        summary="Get Feedback",
        tags=["Client Feedback"],
    ),
    destroy=extend_schema(
        description="Delete feedback",
        summary="Delete Feedback",
        tags=["Client Feedback"],
    ),
)
class ClientFeedbackViewSet(viewsets.ModelViewSet):
    """ViewSet for managing client feedback"""

    queryset = ClientFeedback.objects.all()
    serializer_class = ClientFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]  # Added put and patch

    def get_queryset(self):
        """Filter feedback based on user role"""
        user = self.request.user
        queryset = ClientFeedback.objects.select_related(
            "therapist", "patient", "appointment"
        )

        if user.user_type == "therapist":
            return queryset.filter(therapist=user)
        elif user.user_type == "patient":
            return queryset.filter(patient=user)
        return ClientFeedback.objects.none()

    def create(self, request, *args, **kwargs):
        """Submit new feedback"""
        if request.user.user_type != "patient":
            return Response(
                {"error": "Only patients can submit feedback"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)

                headers = self.get_success_headers(serializer.data)
                return Response(
                    serializer.data, status=status.HTTP_201_CREATED, headers=headers
                )
        except Exception as e:
            logger.error(f"Error creating feedback: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Update feedback"""
        instance = self.get_object()

        # Only allow patients to update their own feedback
        if request.user.user_type != "patient" or instance.patient != request.user:
            return Response(
                {"error": "You can only update your own feedback"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            with transaction.atomic():
                partial = kwargs.pop("partial", False)
                serializer = self.get_serializer(
                    instance, data=request.data, partial=partial
                )
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error updating feedback: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """Delete feedback"""
        instance = self.get_object()

        # Only allow patients to delete their own feedback
        if request.user.user_type != "patient" or instance.patient != request.user:
            return Response(
                {"error": "You can only delete your own feedback"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting feedback: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not delete feedback"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
