#appointments/permissions.py
from rest_framework import permissions


class IsPatientOrTherapist(permissions.BasePermission):
    """
    Custom permission to only allow patients and therapists to access appointments.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in [
            "patient",
            "therapist",
        ]

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request for patients/therapists,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return (
                request.user == obj.patient.user or request.user == obj.therapist.user
            )

        # Write permissions are only allowed to the owner of the appointment
        if view.action == "confirm":
            return request.user == obj.therapist.user
        elif view.action == "cancel":
            return request.user in [obj.patient.user, obj.therapist.user]
        elif view.action == "complete":
            return request.user == obj.therapist.user

        # For other actions (update, delete), only allow if status is "scheduled"
        return (
            request.user == obj.patient.user or request.user == obj.therapist.user
        ) and obj.status == "scheduled"
