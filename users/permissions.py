# users/permissions.py
from rest_framework import permissions


class IsSuperUserOrSelf(permissions.BasePermission):
    """
    Custom permission to only allow superusers or owners of an object to access it.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return obj.user == request.user
