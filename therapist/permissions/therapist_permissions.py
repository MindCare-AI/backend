# therapist/permissions/therapist_permissions.py
from rest_framework.permissions import BasePermission
from rest_framework import permissions
from rest_framework import viewsets
from therapist.models import TherapistProfile
from therapist.serializers import TherapistProfileSerializer


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "patient"


class IsVerifiedTherapist(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "therapist"
            and hasattr(request.user, "therapist_profile")
            and request.user.therapist_profile.is_verified
        )


class CanAccessTherapistProfile(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.is_superuser:
            return True

        if user.user_type == "therapist":
            return obj.user == user

        if user.user_type == "patient" and obj.is_verified:
            return True

        return False


class IsSuperUserOrSelf(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        if hasattr(obj, "user"):
            is_self = obj.user == request.user
        else:
            is_self = obj == request.user

        return is_self


class IsTherapistOrReadOnly(BasePermission):
    """
    Custom permission to only allow therapists to create/edit notes.
    Read-only access is provided to patients for their own notes.
    """

    def has_permission(self, request, view):
        # Allow read access for authenticated users
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return request.user.is_authenticated

        # Write permissions only for therapists
        return request.user.is_authenticated and request.user.user_type == "therapist"

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            # For therapists - allow if they created the note
            if request.user.user_type == "therapist":
                return obj.therapist == request.user  # Compare with user directly

            # For patients - allow if the note is about them
            elif request.user.user_type == "patient":
                return obj.patient == request.user  # Compare with user directly

            # For admins - allow access
            return request.user.is_staff

        # Write permissions only for therapists who created the note
        return request.user.user_type == "therapist" and obj.therapist == request.user


class TherapistProfileViewSet(viewsets.ModelViewSet):
    queryset = TherapistProfile.objects.all()
    serializer_class = TherapistProfileSerializer
    permission_classes = [IsSuperUserOrSelf]
