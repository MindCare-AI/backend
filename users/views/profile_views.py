# users/views/profile_views.py

from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema_view, extend_schema
from patient.models.patient_profile import PatientProfile
from patient.serializers.patient_profile import PatientProfileSerializer
from therapist.serializers.therapist_profile import TherapistProfileSerializer
from users.permissions.user import IsSuperUserOrSelf
from django.apps import apps


def get_therapist_profile():
    return apps.get_model("therapist", "TherapistProfile")


@extend_schema_view(
    list=extend_schema(
        description="Get base profile information",
        summary="Get Profile",
        tags=["Profile"],
    ),
)
class BaseProfileViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
    http_method_names = ["get"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return self.model.objects.select_related("user").all()
        return self.model.objects.select_related("user").filter(
            user=self.request.user
        )


@extend_schema_view(
    list=extend_schema(
        description="Get patient profile information",
        summary="Get Patient Profile",
        tags=["Profile"],
    ),
    update=extend_schema(
        description="Update patient profile information",
        summary="Update Patient Profile",
        tags=["Profile"],
    ),
    partial_update=extend_schema(
        description="Partially update profile information",
        summary="Patch Profile",
        tags=["Profile"],
    ),
)
class PatientProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
    http_method_names = ["get", "put", "patch", "delete"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PatientProfile.objects.select_related("user").all()
        return PatientProfile.objects.select_related("user").filter(
            user=self.request.user
        )


@extend_schema_view(
    list=extend_schema(
        description="Get therapist profile information",
        summary="Get Therapist Profile",
        tags=["Profile"],
    ),
    update=extend_schema(
        description="Update therapist profile information",
        summary="Update Therapist Profile",
        tags=["Profile"],
    ),
)
class TherapistProfileViewSet(viewsets.ModelViewSet):
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperUserOrSelf]
    http_method_names = ["get", "put", "patch", "delete"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return get_therapist_profile().objects.select_related("user").all()
        return (
            get_therapist_profile()
            .objects.select_related("user")
            .filter(user=self.request.user)
        )
