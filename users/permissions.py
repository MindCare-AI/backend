from rest_framework import permissions

class IsSuperUserOrSelfMethodBased(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True
        if request.method in ['GET', 'PUT', 'PATCH']:
            return True
        return False

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user