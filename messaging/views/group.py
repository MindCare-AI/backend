# messaging/views/group.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Count
from django.contrib.auth import get_user_model
from django.conf import settings
import logging

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models.group import GroupConversation, GroupMessage
from ..serializers.group import GroupConversationSerializer, GroupMessageSerializer
from ..pagination import CustomMessagePagination
from messaging.permissions import IsParticipantOrModerator
from messaging.throttling import GroupMessageThrottle
from ..services.firebase import push_message  # Add this import

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all group conversations where the authenticated user is a participant.",
        summary="List Group Conversations",
        tags=["Group Conversation"],
    ),
    retrieve=extend_schema(
        description="Retrieve details of a specific group conversation.",
        summary="Retrieve Group Conversation",
        tags=["Group Conversation"],
    ),
    create=extend_schema(
        description="Create a new group conversation and automatically add the creator as a participant and moderator.",
        summary="Create Group Conversation",
        tags=["Group Conversation"],
    ),
    update=extend_schema(
        description="Update details of a group conversation.",
        summary="Update Group Conversation",
        tags=["Group Conversation"],
    ),
    partial_update=extend_schema(
        description="Partially update a group conversation.",
        summary="Patch Group Conversation",
        tags=["Group Conversation"],
    ),
    destroy=extend_schema(
        description="Delete a group conversation.",
        summary="Delete Group Conversation",
        tags=["Group Conversation"],
    ),
)
class GroupConversationViewSet(viewsets.ModelViewSet):
    queryset = GroupConversation.objects.all()
    serializer_class = GroupConversationSerializer
    permission_classes = [IsParticipantOrModerator]
    throttle_classes = [GroupMessageThrottle]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.none()
        return (
            self.queryset.filter(participants=user)
            .prefetch_related("participants", "moderators")
            .annotate(
                participant_count=Count("participants"),
                message_count=Count("messages")
            )
        )

    @transaction.atomic
    def perform_create(self, serializer):
        """Create group with atomic transaction (notifications removed)"""
        try:
            max_groups = getattr(settings, "MAX_GROUPS_PER_USER", 10)
            user_groups = GroupConversation.objects.filter(
                participants=self.request.user
            ).count()
            if user_groups >= max_groups:
                raise ValidationError(f"Maximum group limit ({max_groups}) reached")

            instance = serializer.save()
            instance.participants.add(self.request.user)
            instance.moderators.add(self.request.user)

            logger.info(
                f"Group conversation {instance.id} created by user {self.request.user.id}"
            )
            return instance

        except Exception as e:
            logger.error(f"Group creation failed: {str(e)}")
            raise ValidationError(f"Failed to create group: {str(e)}")

    @extend_schema(
        description="Add a user as a moderator to the group (notifications removed).",
        summary="Add Moderator",
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"])
    def add_moderator(self, request, pk=None):
        group = self.get_object()
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "You don't have permission to add moderators."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user = get_object_or_404(get_user_model(), id=request.data.get("user_id"))
        if not group.participants.filter(id=user.id).exists():
            return Response(
                {
                    "detail": "User must be a participant before being promoted to moderator."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        group.moderators.add(user)
        return Response(
            {"detail": f"User {user.username} is now a moderator."},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        description="List all moderators of the group.",
        summary="List Moderators",
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["get"])
    def moderators(self, request, pk=None):
        group = self.get_object()
        moderator_data = [
            {
                "id": mod.id,
                "username": mod.username,
                "first_name": mod.first_name,
                "last_name": mod.last_name,
                "email": mod.email,
            }
            for mod in group.moderators.all()
        ]
        return Response(moderator_data)

    @action(detail=True, methods=["post"])
    def add_participant(self, request, pk=None):
        """Add participant to group (notifications removed)"""
        try:
            group = self.get_object()

            # Validate moderator permission
            if not group.moderators.filter(id=request.user.id).exists():
                return Response(
                    {"error": "Only moderators can add participants"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user_id = request.data.get("user_id")
            user = get_object_or_404(get_user_model(), id=user_id)

            if group.participants.count() >= settings.MAX_PARTICIPANTS_PER_GROUP:
                return Response(
                    {"error": "Maximum participant limit reached"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            group.participants.add(user)
            return Response(
                {"message": f"Added {user.username} to group"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error adding participant: {str(e)}")
            return Response(
                {"error": "Failed to add participant"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def remove_participant(self, request, pk=None):
        """Remove participant with proper validation (notifications removed)"""
        try:
            group = self.get_object()
            user_id = request.data.get("user_id")
            user = get_object_or_404(get_user_model(), id=user_id)

            if not (
                request.user.id == user_id
                or group.moderators.filter(id=request.user.id).exists()
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            group.participants.remove(user)
            group.moderators.remove(user)

            return Response(
                {"message": f"Removed {user.username} from group"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error removing participant: {str(e)}")
            return Response(
                {"error": "Failed to remove participant"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def pin_message(self, request, pk=None):
        group = self.get_object()
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "Only moderators can pin messages"},
                status=status.HTTP_403_FORBIDDEN,
            )

        pinned_message_id = request.data.get("message_id")
        if not pinned_message_id:
            return Response(
                {"detail": "Message ID is required to pin a message."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group.pinned_message_id = pinned_message_id
        group.save()
        return Response(
            {"detail": "Message pinned successfully."}, status=status.HTTP_200_OK
        )

    @extend_schema(exclude=True)
    @action(detail=False, methods=["post"])
    def create_anonymous(self, request):
        """
        Create an anonymous group conversation. If a name is not provided, a default
        anonymous name is set and the conversation is marked as private.
        """
        data = request.data.copy()
        # Set default name if not provided
        if not data.get("name", "").strip():
            data["name"] = "Anonymous Conversation"
        # Force conversation to be private
        data["is_private"] = True
        # If participants list is not provided, set it as empty (perform_create will add request.user)
        if "participants" not in data:
            data["participants"] = []
            
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        conversation = self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GroupMessageViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMessageSerializer
    permission_classes = [IsParticipantOrModerator]
    pagination_class = CustomMessagePagination

    def get_queryset(self):
        return (
            GroupMessage.objects.filter(conversation__participants=self.request.user)
            .select_related("sender", "conversation")
            .prefetch_related(
                Prefetch("conversation__participants"), 
                Prefetch("read_by")
            )
            .order_by("-timestamp")
        )

    def create(self, request, *args, **kwargs):
        try:
            # Log the incoming request data
            logger.debug(f"Creating group message with data: {request.data}")
            
            # Validate the request data
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Validation error: {serializer.errors}")
                return Response(
                    {"error": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get and verify conversation exists
            conversation_id = request.data.get('conversation')
            if not conversation_id:
                return Response(
                    {"error": "Conversation ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Check if conversation exists and user is participant
                conversation = GroupConversation.objects.select_related().get(
                    id=conversation_id
                )
                if not conversation.participants.filter(id=request.user.id).exists():
                    return Response(
                        {"error": "You are not a participant in this conversation"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Create the message
                message = serializer.save(
                    sender=request.user,
                    conversation=conversation
                )
                logger.info(f"Created group message {message.id} in conversation {conversation.id}")

                # Prepare and push Firebase notification
                try:
                    message_data = {
                        'id': str(message.id),
                        'content': message.content,
                        'sender': message.sender.id,
                        'timestamp': message.timestamp.isoformat(),
                        'conversation_id': message.conversation.id,
                        'message_type': getattr(message, "message_type", "text"),
                    }
                    push_message(conversation.id, message_data)
                except Exception as e:
                    logger.error(f"Failed to push Firebase notification: {str(e)}")
                    # Continue execution even if push notification fails
                
                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED
                )

            except GroupConversation.DoesNotExist:
                logger.error(f"Group conversation {conversation_id} not found")
                return Response(
                    {"error": f"Group conversation {conversation_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

        except ValidationError as e:
            logger.error(f"Validation error creating message: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error creating message: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if (
            instance.sender != request.user
            and not instance.conversation.moderators.filter(id=request.user.id).exists()
        ):
            return Response(
                {"detail": "You do not have permission to edit this message."},
                status=status.HTTP_403_FORBIDDEN,
            )

        response = super().update(request, *args, **kwargs)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if (
            instance.sender != request.user
            and not instance.conversation.moderators.filter(id=request.user.id).exists()
        ):
            return Response(
                {"detail": "You do not have permission to delete this message."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(exclude=True)
    @action(detail=True, methods=["get"])
    def edit_history(self, request, pk=None):
        # Placeholder implementation for edit history.
        return Response(
            {"detail": "Edit history not implemented."},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    @extend_schema(
        description="Add a reaction to a group message.",
        summary="Add Reaction",
        tags=["Group Message"],
    )
    @action(detail=True, methods=["post"])
    def add_reaction(self, request, pk=None):
        """Add a reaction to a message."""
        try:
            message = self.get_object()
            reaction = request.data.get("reaction")

            if not reaction:
                return Response(
                    {"error": "Reaction is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Assuming a `reactions` field exists on the message model
            message.reactions.create(user=request.user, reaction=reaction)
            return Response(
                {"message": "Reaction added successfully."},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error adding reaction: {str(e)}")
            return Response(
                {"error": "Failed to add reaction."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Remove a reaction from a group message.",
        summary="Remove Reaction",
        tags=["Group Message"],
    )
    @action(detail=True, methods=["post"])
    def remove_reaction(self, request, pk=None):
        """Remove a reaction from a message."""
        try:
            message = self.get_object()
            reaction = request.data.get("reaction")

            if not reaction:
                return Response(
                    {"error": "Reaction is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Assuming a `reactions` field exists on the message model
            reaction_instance = message.reactions.filter(
                user=request.user, reaction=reaction
            ).first()

            if not reaction_instance:
                return Response(
                    {"error": "Reaction not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            reaction_instance.delete()
            return Response(
                {"message": "Reaction removed successfully."},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error removing reaction: {str(e)}")
            return Response(
                {"error": "Failed to remove reaction."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
