# therapist/permissions.py
from rest_framework.permissions import BasePermission
from rest_framework import permissions


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "patient"


class IsVerifiedTherapist(permissions.BasePermission):
    """Allow access only to verified therapists"""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "therapist"
            and hasattr(request.user, "therapist_profile")
            and request.user.therapist_profile.is_verified
        )


class CanAccessTherapistProfile(permissions.BasePermission):
    """Control access to therapist profiles"""

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admins can access all profiles
        if user.is_superuser:
            return True

        # Therapists can only access their own profile
        if user.user_type == "therapist":
            return obj.user == user

        # Patients can view verified therapist profiles
        if user.user_type == "patient" and obj.is_verified:
            return True

        return False
