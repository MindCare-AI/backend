# messaging/permissions.py
from rest_framework.permissions import BasePermission


class IsPatient(BasePermission):
    """
    Custom permission to only allow patients to access chatbot
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.user_type == "patient"
        )


class IsTherapist(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "therapist"
