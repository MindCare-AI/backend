# messaging/permissions.py
from rest_framework.permissions import BasePermission
from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


class IsTherapist(BasePermission):
    """
    Custom permission to only allow therapists to access therapy-specific features
    """

    def has_permission(self, request, view):
        return (
            request.user
            and hasattr(request.user, "user_type")
            and request.user.user_type == "therapist"
        )


class IsParticipant(BasePermission):
    """
    Custom permission to only allow participants of a conversation to access it
    """

    def has_object_permission(self, request, view, obj):
        return request.user in obj.participants.all()


class IsMessageOwner(BasePermission):
    """
    Custom permission to only allow message owners to modify their messages
    """

    def has_object_permission(self, request, view, obj):
        return obj.sender == request.user


class IsModerator(BasePermission):
    """
    Custom permission to allow moderators to manage conversations
    """

    def has_permission(self, request, view):
        return (
            request.user
            and hasattr(request.user, "is_moderator")
            and request.user.is_moderator
        )


class CanSendMessage(BasePermission):
    """
    Custom permission to check if user can send messages in a conversation
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not obj:
            return False
        return request.user in obj.participants.all() and not getattr(
            request.user, "is_muted", False
        )


class IsParticipantOrModerator(permissions.BasePermission):
    """
    Custom permission to only allow participants or moderators of a conversation.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        is_moderator = hasattr(user, "is_moderator") and user.is_moderator
        is_participant = user in obj.participants.all()
        return is_moderator or is_participant
