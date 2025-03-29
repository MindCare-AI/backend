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


from rest_framework import permissions

class IsParticipantOrModerator(permissions.BasePermission):
    """
    Custom permission to only allow participants or moderators of a conversation.
    """

    def has_permission(self, request, view):
        # Always allow GET, HEAD, OPTIONS requests
        if request.method in permissions.SAFE_METHODS:
            # For detail views (retrieve, update, delete)
            if getattr(view, 'detail', False) and view.kwargs.get('pk'):
                return True  # We'll do the check in has_object_permission
            # For list views
            return request.user.is_authenticated
        # For unsafe methods like POST, PUT, PATCH
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Get the conversation object directly or via the message
        if hasattr(obj, 'conversation'):
            conversation = obj.conversation
        else:
            conversation = obj
            
        # Check if user is a participant
        try:
            user_is_participant = conversation.participants.filter(id=request.user.id).exists()
        except Exception as e:
            logger.error(f"Error checking participant status: {str(e)}")
            user_is_participant = False
            
        # Check if user is a moderator (for group conversations)
        try:
            user_is_moderator = hasattr(conversation, 'moderators') and conversation.moderators.filter(id=request.user.id).exists()
        except Exception as e:
            logger.error(f"Error checking moderator status: {str(e)}")
            user_is_moderator = False
            
        # For GET requests, allow if user is a participant
        if request.method in permissions.SAFE_METHODS:
            return user_is_participant
            
        # For PUT/PATCH/DELETE, check if it's the message owner or a moderator
        if hasattr(obj, 'sender') and request.method in ['PUT', 'PATCH', 'DELETE']:
            return obj.sender == request.user or user_is_moderator
            
        # For conversation-level actions, check moderator status
        if hasattr(view, 'action') and view.action in ['add_participant', 'remove_participant', 'add_moderator', 'pin_message']:
            return user_is_moderator
            
        # Default: allow if participant
        return user_is_participant
