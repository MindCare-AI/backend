# patient/views.py
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django_filters import rest_framework as django_filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import PatientProfile, MoodLog, HealthMetric, MedicalHistoryEntry
from .serializers import (
    PatientProfileSerializer,
    MoodLogSerializer,
    HealthMetricSerializer,
    MedicalHistorySerializer,
)
import logging
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class PatientProfileFilter(django_filters.FilterSet):
    blood_type = django_filters.CharFilter(lookup_expr="exact")
    condition = django_filters.CharFilter(method="filter_condition")
    appointment_after = django_filters.DateTimeFilter(
        field_name="next_appointment", lookup_expr="gte"
    )

    class Meta:
        model = PatientProfile
        fields = ["blood_type", "condition", "appointment_after"]

    def filter_condition(self, queryset, name, value):
        return queryset.filter(
            Q(medical_history__icontains=value)
            | Q(current_medications__icontains=value)
        )


@extend_schema_view(
    list=extend_schema(
        description="List patient profiles with filtering options",
        tags=["Patient Profiles"],
    ),
    retrieve=extend_schema(
        description="Get detailed patient profile", tags=["Patient Profiles"]
    ),
)
class PatientProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = PatientProfileFilter
    search_fields = ["medical_history", "current_medications"]
    ordering_fields = ["created_at", "next_appointment"]
    http_method_names = ["get", "put", "patch", "delete"]

    def get_queryset(self):
        queryset = PatientProfile.objects.select_related("user")

        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)

        return queryset

    @action(detail=True, methods=["get"])
    def appointments(self, request, pk=None):
        profile = self.get_object()
        return Response(
            {
                "last_appointment": profile.last_appointment,
                "next_appointment": profile.next_appointment,
                "has_upcoming": bool(profile.next_appointment),
            }
        )


@extend_schema_view(
    list=extend_schema(
        description="List mood log entries for the authenticated patient.",
        summary="List Mood Logs",
        tags=["Mood Log"],
    ),
    retrieve=extend_schema(
        description="Retrieve a specific mood log entry.",
        summary="Retrieve Mood Log",
        tags=["Mood Log"],
    ),
    create=extend_schema(
        description="Create a new mood log entry for the patient.",
        summary="Create Mood Log",
        tags=["Mood Log"],
    ),
)
class MoodLogViewSet(viewsets.ModelViewSet):
    serializer_class = MoodLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MoodLog.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class HealthMetricViewSet(viewsets.ModelViewSet):
    serializer_class = HealthMetricSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Filter by patient profile related to the current user
        return HealthMetric.objects.filter(patient__user=self.request.user)


class MedicalHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = MedicalHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MedicalHistoryEntry.objects.filter(patient__user=self.request.user)
