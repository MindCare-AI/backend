# notifications/permissions.py
from rest_framework.permissions import BasePermission


class IsNotificationOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user

class IsParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.participants.filter(id=request.user.id).exists()  # Optimized
