# users/views/preferences_views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema_view, extend_schema
from users.models.preferences import UserPreferences
from users.serializers.preferences import UserPreferencesSerializer
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


@extend_schema_view(
    retrieve=extend_schema(
        description="Get user preferences",
        summary="Get User Preferences",
        tags=["Preferences"],
    ),
    update=extend_schema(
        description="Update user preferences",
        summary="Update Preferences",
        tags=["Preferences"],
    ),
    partial_update=extend_schema(
        description="Partially update user preferences",
        summary="Patch Preferences",
        tags=["Preferences"],
    ),
)
class UserPreferencesViewSet(viewsets.ModelViewSet):
    serializer_class = UserPreferencesSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        preferences, created = UserPreferences.objects.get_or_create(
            user=self.request.user
        )
        return preferences

    def get_queryset(self):
        return UserPreferences.objects.filter(user=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        try:
            instance = serializer.save()
            logger.info(f"Updated preferences for user {self.request.user.id}")
            return instance
        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}")
            raise