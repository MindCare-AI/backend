# therapist/views/appointment_views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from therapist.models.appointment import Appointment

from therapist.serializers.appointment import AppointmentSerializer
import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List user's appointments",
        tags=["Appointments"],
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                enum=["scheduled", "confirmed", "cancelled", "completed"],
                description="Filter by appointment status",
            )
        ],
    ),
    retrieve=extend_schema(
        description="Get appointment details", tags=["Appointments"]
    ),
    update=extend_schema(description="Update appointment", tags=["Appointments"]),
    partial_update=extend_schema(
        description="Patch appointment", tags=["Appointments"]
    ),
)
class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "put", "delete"]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == "therapist":
            return Appointment.objects.filter(
                therapist=user.therapist_profile
            )  # ✅ Use therapist profile
        elif user.user_type == "patient":
            return Appointment.objects.filter(
                patient=user.patient_profile
            )  # ✅ Use patient profile
        return Appointment.objects.none()

    @extend_schema(
        description="Confirm an appointment",
        summary="Confirm Appointment",
        tags=["Appointments"],
        responses={
            200: AppointmentSerializer,
            403: {"description": "Only therapist can confirm appointments"},
        },
    )
    @action(detail=True, methods=["get", "post"])
    def confirm(self, request, pk=None):
        # GET is provided only so that the DRF Browsable API renders a form.
        if request.method == "GET":
            return Response(
                {"detail": "This endpoint confirms an appointment. Please use POST."}
            )

        appointment = self.get_object()
        if appointment.therapist.user != request.user:
            return Response(
                {"error": "Only the therapist can confirm appointments"},
                status=status.HTTP_403_FORBIDDEN,
            )
        appointment.status = "confirmed"
        appointment.save()
        serializer = self.get_serializer(appointment)

        return Response(serializer.data)

    @extend_schema(
        description="Cancel an appointment",
        summary="Cancel Appointment",
        tags=["Appointments"],
        responses={
            200: AppointmentSerializer,
            403: {"description": "Only therapist or patient can cancel appointments"},
        },
    )
    @action(detail=True, methods=["get", "post"])
    def cancel(self, request, pk=None):
        # Provide GET method for the Browsable API.
        if request.method == "GET":
            return Response(
                {"detail": "This endpoint cancels an appointment. Please use POST."}
            )

        appointment = self.get_object()
        if (
            appointment.therapist.user != request.user
            and appointment.patient.user != request.user
        ):
            return Response(
                {"error": "Only the therapist or patient can cancel appointments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        appointment.status = "cancelled"
        appointment.save()
        serializer = self.get_serializer(appointment)

        return Response(serializer.data)
