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
    Permission to only allow participants or moderators of a conversation to access it.
    """

    def has_permission(self, request, view):
        # Allow all authenticated users for list/create
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Check if user is participant
        if hasattr(obj, "participants"):
            is_participant = obj.participants.filter(id=request.user.id).exists()

            # For safe methods (GET, HEAD, OPTIONS) being a participant is enough
            if request.method in permissions.SAFE_METHODS and is_participant:
                return True

            # For modify/delete methods, check if user is moderator (for group conversations)
            if hasattr(obj, "moderators"):
                is_moderator = obj.moderators.filter(id=request.user.id).exists()
                return is_moderator

            # For one-to-one conversations, being a participant is enough for all operations
            return is_participant

        # For message objects, check if user is participant in the conversation
        if hasattr(obj, "conversation"):
            if hasattr(obj.conversation, "participants"):
                is_participant = obj.conversation.participants.filter(
                    id=request.user.id
                ).exists()

                # For safe methods, being a participant is enough
                if request.method in permissions.SAFE_METHODS:
                    return is_participant

                # For modify/delete, check if user is sender or moderator
                is_sender = obj.sender == request.user

                # If group conversation, check if user is moderator
                if hasattr(obj.conversation, "moderators"):
                    is_moderator = obj.conversation.moderators.filter(
                        id=request.user.id
                    ).exists()
                    return is_sender or is_moderator

                # For one-to-one messages, only allow sender to modify
                return is_sender

        return False


class IsMessageSender(permissions.BasePermission):
    """
    Permission to only allow the sender of a message to modify it.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # For safe methods, check if user is participant in the conversation
        if request.method in permissions.SAFE_METHODS:
            if hasattr(obj, "conversation") and hasattr(
                obj.conversation, "participants"
            ):
                return obj.conversation.participants.filter(id=request.user.id).exists()

        # For modify/delete, check if user is the sender
        return obj.sender == request.user
