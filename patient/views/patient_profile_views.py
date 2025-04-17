# patient/views/patient_profile_views.py
from rest_framework import viewsets, permissions, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as django_filters
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)
from patient.models.patient_profile import PatientProfile
from patient.serializers.patient_profile import PatientProfileSerializer
from patient.filters.patient_profile_filters import PatientProfileFilter
import logging
from media_handler.models import MediaFile
from users.permissions.user import IsSuperUserOrSelf

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="Retrieve list of patient profiles.",
        summary="List Patient Profiles",
        tags=["Patient Profile"],
    ),
    retrieve=extend_schema(
        description="Retrieve detailed patient profile information.",
        summary="Retrieve Patient Profile",
        tags=["Patient Profile"],
    ),
    update=extend_schema(
        description="Update patient profile information.",
        summary="Update Patient Profile",
        tags=["Patient Profile"],
    ),
    partial_update=extend_schema(
        description="Partially update patient profile fields.",
        summary="Patch Patient Profile",
        tags=["Patient Profile"],
    ),
)
class PatientProfileViewSet(viewsets.ModelViewSet):
    lookup_field = "pk"  # Changed from "unique_id" to "pk"
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

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)  # Return updated profile data

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve appointment details from a patient profile.",
        summary="Get Appointments",
        responses=OpenApiResponse(response=PatientProfileSerializer),
        tags=["Patient Profile"],
    )
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

    @extend_schema(
        description="Upload a file associated with the patient profile.",
        summary="Upload File",
        request=OpenApiParameter(
            name="file", location="form", type="file", required=True
        ),
        responses={
            200: {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "file_id": {"type": "integer"},
                },
            }
        },
        tags=["Patient Profile"],
    )
    @action(detail=True, methods=["post"])
    def upload_file(self, request, pk=None):
        patient_profile = request.user.patientprofile
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "No file uploaded"}, status=400)
        media_file = MediaFile.objects.create(
            file=uploaded_file,
            media_type="document",
            content_object=patient_profile,
            uploaded_by=request.user,
        )
        return Response({"status": "file uploaded", "file_id": media_file.id})


class PublicPatientListView(generics.ListAPIView):
    """
    Lists all patient profiles with detailed information.
    """

    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = PatientProfileFilter
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self):
        return PatientProfile.objects.select_related("user").all().order_by("id")
