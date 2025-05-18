# core/permissions.py
from rest_framework import permissions


class IsPatientOrTherapist(permissions.BasePermission):
    """
    Custom permission to check if user is a patient or therapist.
    """

    def has_permission(self, request, view):
        return request.user and request.user.user_type in ["patient", "therapist"]

    def has_object_permission(self, request, view, obj):
        if not request.user:
            return False

        if hasattr(obj, "patient") and hasattr(obj.patient, "user"):
            if request.user == obj.patient.user:
                return True

        if hasattr(obj, "therapist") and hasattr(obj.therapist, "user"):
            if request.user == obj.therapist.user:
                return True

        return False
