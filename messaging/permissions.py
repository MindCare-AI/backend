# messaging/permissions.py
from rest_framework.permissions import BasePermission
import logging

logger = logging.getLogger(__name__)


class IsPatient(BasePermission):
    """
    Custom permission to only allow patients to access chatbot and patient-specific features
    """

    def has_permission(self, request, view):
        try:
            return bool(
                request.user
                and request.user.is_authenticated
                and request.user.user_type == "patient"
            )
        except Exception as e:
            logger.error(f"Error checking patient permission: {str(e)}")
            return False


class IsTherapist(BasePermission):
    """
    Custom permission to only allow therapists to access therapy-specific features
    """

    def has_permission(self, request, view):
        try:
            return bool(
                request.user
                and request.user.is_authenticated
                and request.user.user_type == "therapist"
            )
        except Exception as e:
            logger.error(f"Error checking therapist permission: {str(e)}")
            return False


class IsParticipant(BasePermission):
    """
    Custom permission to only allow participants of a conversation to access it
    """

    def has_object_permission(self, request, view, obj):
        try:
            return request.user in obj.participants.all()
        except Exception as e:
            logger.error(f"Error checking participant permission: {str(e)}")
            return False


class IsMessageOwner(BasePermission):
    """
    Custom permission to only allow message owners to modify their messages
    """

    def has_object_permission(self, request, view, obj):
        try:
            return obj.sender == request.user
        except Exception as e:
            logger.error(f"Error checking message owner permission: {str(e)}")
            return False


class IsModerator(BasePermission):
    """
    Custom permission to allow moderators to manage conversations
    """

    def has_object_permission(self, request, view, obj):
        try:
            # Check if user is a moderator and hasn't been removed
            return (
                request.user in obj.moderators.all()
                and not obj.removed_moderators.filter(id=request.user.id).exists()
            )
        except Exception as e:
            logger.error(f"Error checking moderator permission: {str(e)}")
            return False


class CanSendMessage(BasePermission):
    """
    Custom permission to check if user can send messages in a conversation
    """

    def has_object_permission(self, request, view, obj):
        try:
            user = request.user
            # Check if conversation is active and user isn't blocked
            return (
                not obj.is_archived
                and user in obj.participants.all()
                and not obj.blocked_users.filter(id=user.id).exists()
            )
        except Exception as e:
            logger.error(f"Error checking message permission: {str(e)}")
            return False


class IsParticipantOrModerator(BasePermission):
    """
    Custom permission to allow access if the user is either
    a participant or a moderator of the conversation.
    """

    def has_object_permission(self, request, view, obj):
        try:
            return (
                request.user in obj.participants.all()
                or request.user in obj.moderators.all()
            )
        except Exception as e:
            logger.error(f"Error checking IsParticipantOrModerator: {str(e)}")
            return False
