# users/views/settings_views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema_view
from users.models.settings import UserSettings
from users.serializers.settings import UserSettingsSerializer
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="Get user settings including theme and notification configurations",
        summary="Get User Settings",
        tags=["Settings"],
    ),
    update=extend_schema(
        description="Update user settings", summary="Update Settings", tags=["Settings"]
    ),
    partial_update=extend_schema(
        description="Partially update user settings",
        summary="Patch Settings",
        tags=["Settings"],
    ),
)
class UserSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return UserSettings.objects.all()
        return UserSettings.objects.filter(user=self.request.user)

    def get_object(self):
        user = self.request.user
        settings_obj, created = UserSettings.objects.get_or_create(user=user)
        return settings_obj

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
