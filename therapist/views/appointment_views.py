# therapist/views/appointment_views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from appointments.models import Appointment
from appointments.serializers import AppointmentSerializer
from therapist.permissions.therapist_permissions import IsVerifiedTherapist
import logging

logger = logging.getLogger(__name__)

MINIMUM_NOTICE_HOURS = 24  # Minimum hours required for scheduling/rescheduling
MAXIMUM_DAILY_APPOINTMENTS = 8  # Maximum appointments per day for a therapist


@extend_schema_view(
    list=extend_schema(
        description="List all appointments",
        summary="List Appointments",
        tags=["Appointments"],
    ),
)
class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Appointment.objects.all()
        elif user.user_type == "therapist":
            return Appointment.objects.filter(therapist__user=user)
        else:
            return Appointment.objects.filter(patient__user=user)

    def validate_appointment_time(
        self, appointment_date, therapist_profile, appointment_id=None
    ):
        # Check minimum notice period
        notice_period = appointment_date - timezone.now()
        if notice_period < timedelta(hours=MINIMUM_NOTICE_HOURS):
            raise ValidationError(
                f"Appointments must be scheduled at least {MINIMUM_NOTICE_HOURS} hours in advance"
            )

        # Check therapist availability
        if not therapist_profile.check_availability(appointment_date):
            raise ValidationError("Therapist is not available at this time")

        # Count daily appointments excluding the current one being rescheduled
        appointments_query = Appointment.objects.filter(
            therapist=therapist_profile,
            appointment_date__date=appointment_date.date(),
            status__in=["scheduled", "confirmed"],
        )
        if appointment_id:
            appointments_query = appointments_query.exclude(id=appointment_id)

        if appointments_query.count() >= MAXIMUM_DAILY_APPOINTMENTS:
            raise ValidationError(
                f"Therapist has reached maximum daily appointments ({MAXIMUM_DAILY_APPOINTMENTS})"
            )

    @extend_schema(
        description="Reschedule an existing appointment",
        summary="Reschedule Appointment",
        tags=["Appointments"],
    )
    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        try:
            appointment = self.get_object()
            new_date = request.data.get("appointment_date")

            if not new_date:
                return Response(
                    {"error": "New appointment date is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            new_date = timezone.datetime.fromisoformat(new_date.replace("Z", "+00:00"))

            # Validate the new appointment time
            self.validate_appointment_time(
                new_date, appointment.therapist, appointment.id
            )

            with transaction.atomic():
                old_date = appointment.appointment_date
                appointment.appointment_date = new_date
                appointment.status = "rescheduled"
                appointment.save()

                logger.info(
                    f"Appointment {appointment.id} rescheduled from {old_date} to {new_date} "
                    f"by {request.user.username}"
                )

                return Response(
                    {
                        "message": "Appointment rescheduled successfully",
                        "appointment": AppointmentSerializer(appointment).data,
                    }
                )

        except Exception as e:
            logger.error(f"Error rescheduling appointment: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        description="Confirm an appointment",
        summary="Confirm Appointment",
        tags=["Appointments"],
    )
    @action(detail=True, methods=["post"], permission_classes=[IsVerifiedTherapist])
    def confirm(self, request, pk=None):
        try:
            appointment = self.get_object()

            if appointment.status != "scheduled":
                return Response(
                    {"error": "Only scheduled appointments can be confirmed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            appointment.status = "confirmed"
            appointment.save()

            logger.info(
                f"Appointment {appointment.id} confirmed by therapist {request.user.username}"
            )

            return Response(
                {
                    "message": "Appointment confirmed successfully",
                    "appointment": AppointmentSerializer(appointment).data,
                }
            )

        except Exception as e:
            logger.error(f"Error confirming appointment: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
