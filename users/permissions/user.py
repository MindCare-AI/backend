# users/permissions/user.py
from rest_framework import permissions
import logging
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class IsSuperUserOrSelf(permissions.BasePermission):
    """
    Permission class to allow only superusers or the user themselves to access an object.
    """
    def has_object_permission(self, request, view, obj):
        # Superusers always have permission
        if request.user.is_superuser:
            return True

        # Check if object has a user attribute or is a user object
        if hasattr(obj, "user"):
            is_self = obj.user == request.user
        else:
            is_self = obj == request.user

        logger.debug(
            f"Permission check: user={request.user.username}, is_self={is_self}"
        )
        return is_self


 
