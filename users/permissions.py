# users/permissions.py
from rest_framework import permissions
import logging
from rest_framework.permissions import BasePermission


logger = logging.getLogger(__name__)


class IsSuperUserOrSelf(permissions.BasePermission):
    """
    Allow access to superusers or the user themselves.
    """

    def has_object_permission(self, request, view, obj):
        # Check if user is superuser
        if request.user.is_superuser:
            return True

        # Check if the object is the user themselves
        # This handles both the CustomUser case and related profile models
        if hasattr(obj, "user"):
            is_self = obj.user == request.user
        else:
            is_self = obj == request.user

        logger.debug(
            f"Permission check: user={request.user.username}, is_self={is_self}"
        )
        return is_self


class IsTherapistForPatient(permissions.BasePermission):
    """
    Allow access to a patient's data only to their assigned therapist.
    """

    def has_object_permission(self, request, view, obj):
        # Superusers always have permission
        if request.user.is_superuser:
            return True

        # If the object is a patient profile, check if the requester is their therapist
        if hasattr(obj, "user") and obj.user.user_type == "patient":
            # This would need to be adapted based on your session/appointment model
            # that links patients to therapists
            from appointments.models import Appointment

            is_therapist = Appointment.objects.filter(
                patient=obj.user,
                therapist=request.user,
                status__in=["scheduled", "completed", "in_progress"],
            ).exists()

            logger.debug(
                f"Therapist permission check: therapist={request.user.username}, patient={obj.user.username}, access_granted={is_therapist}"
            )
            return is_therapist

        return False


class CanSetUserType(BasePermission):
    """
    Permission to only allow users to set their type once
    """

    def has_permission(self, request, view):
        user = request.user
        # Allow if user type not set or user is superuser
        return user.is_authenticated and (user.user_type is None or user.is_superuser)
