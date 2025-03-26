#mood/views.py
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from mood.models import MoodLog
from mood.serializers import MoodLogSerializer
from rest_framework.exceptions import ValidationError

@extend_schema_view(
    list=extend_schema(
        description="List all mood logs for the authenticated user.",
        summary="List Mood Logs",
        tags=["Mood"],
        responses={200: MoodLogSerializer(many=True)},
    ),
    retrieve=extend_schema(
        description="Retrieve details of a specific mood log.",
        summary="Retrieve Mood Log",
        tags=["Mood"],
        responses={200: MoodLogSerializer},
    ),
    create=extend_schema(
        description="Create a new mood log.",
        summary="Create Mood Log",
        tags=["Mood"],
        responses={201: MoodLogSerializer},
    ),
    update=extend_schema(
        description="Update an existing mood log.",
        summary="Update Mood Log",
        tags=["Mood"],
        responses={200: MoodLogSerializer},
    ),
    partial_update=extend_schema(
        description="Partially update an existing mood log.",
        summary="Partial Update Mood Log",
        tags=["Mood"],
        responses={200: MoodLogSerializer},
    ),
    destroy=extend_schema(
        description="Delete a mood log.",
        summary="Delete Mood Log",
        tags=["Mood"],
        responses={204: None},
    ),
)
class MoodLogViewSet(viewsets.ModelViewSet):
    serializer_class = MoodLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MoodLog.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # Optional: override update to allow partial updates on PUT requests
    def update(self, request, *args, **kwargs):
        partial = True  # Force partial update on PUT
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
