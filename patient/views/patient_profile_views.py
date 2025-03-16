# patient/views/patient_profile_views.py
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as django_filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from patient.models.patient_profile import PatientProfile
from patient.serializers.patient_profile import PatientProfileSerializer
from patient.filters.patient_profile_filters import PatientProfileFilter
import logging
from media_handler.models import MediaFile
from users.permissions.user import IsSuperUserOrSelf

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="Get patient profile information",
        summary="Get Patient Profile",
        tags=["Patient Profile"],
    ),
    retrieve=extend_schema(
        description="Get detailed patient profile", tags=["Patient Profiles"]
    ),
    update=extend_schema(
        description="Update patient profile information",
        summary="Update Patient Profile",
        tags=["Patient Profile"],
    ),
    partial_update=extend_schema(
        description="Partially update profile information",
        summary="Patch Profile",
        tags=["Patient Profile"],
    ),
)
class PatientProfileViewSet(viewsets.ModelViewSet):
    lookup_field = "unique_id"  # Use unique_id for lookups
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
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
        if self.request.user.is_superuser:
            return PatientProfile.objects.select_related("user").all()
        return PatientProfile.objects.select_related("user").filter(
            user=self.request.user
        )

    @action(detail=True, methods=["get"])
    def appointments(self, request, unique_id=None):
        profile = self.get_object()
        return Response(
            {
                "last_appointment": profile.last_appointment,
                "next_appointment": profile.next_appointment,
                "has_upcoming": bool(profile.next_appointment),
            }
        )

    @action(detail=True, methods=["post"])
    def upload_file(self, request, unique_id=None):
        patient_profile = request.user.patientprofile
        uploaded_file = request.FILES.get("file")

        media_file = MediaFile.objects.create(
            file=uploaded_file,
            media_type="document",
            content_object=patient_profile,
            uploaded_by=request.user,
        )
        return Response({"status": "file uploaded", "file_id": media_file.id})
