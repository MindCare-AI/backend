# messaging/views/group.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.conf import settings
import logging

from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
)

from ..models.group import GroupConversation, GroupMessage
from ..serializers.group import GroupConversationSerializer, GroupMessageSerializer
from messaging.permissions import IsParticipantOrModerator
from messaging.throttling import GroupMessageThrottle
from ..mixins.edit_history import EditHistoryMixin
from ..mixins.reactions import ReactionMixin

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
        """Fetch all groups the user is involved in."""
        user = self.request.user
        logger.debug(f"Fetching groups for user: {user.id}")
        groups = GroupConversation.objects.filter(participants=user)
        logger.debug(f"Groups found: {groups.count()}")
        return groups

    def get_serializer_class(self):
        """Return the appropriate serializer class based on the action."""
        if self.action == "add_participant":
            from ..serializers.group import AddParticipantSerializer

            return AddParticipantSerializer
        return super().get_serializer_class()

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
        description="Create a new group conversation. Provide a name and any other allowed fields. The creator is automatically added as a participant and moderator.",
        summary="Create Group Conversation",
        request={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the group conversation",
                },
                # include any additional parameters as needed...
            },
            "required": ["name"],
        },
        responses={
            201: GroupConversationSerializer,
            400: OpenApiResponse(
                description="Bad Request – e.g., missing name or exceeding group limit."
            ),
        },
        examples=[
            OpenApiExample(
                "Valid Request",
                description="A valid request to create a group conversation",
                value={"name": "Test Group Conversation"},
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        description="Add a user as a moderator to the group.",
        summary="Add Moderator",
        request={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "ID of the user to add as moderator.",
                }
            },
            "required": ["user_id"],
        },
        responses={
            200: OpenApiResponse(description="User added as moderator successfully."),
            400: OpenApiResponse(
                description="Bad Request – e.g., user not a participant."
            ),
            403: OpenApiResponse(description="Forbidden – insufficient permission."),
        },
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

    @extend_schema(
        description="Add a participant to the group.",
        summary="Add Participant",
        request={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "ID of the user to add as participant.",
                }
            },
            "required": ["user_id"],
        },
        responses={
            200: OpenApiResponse(
                description="User added as participant successfully or already a member."
            ),
            400: OpenApiResponse(
                description="Bad Request – e.g., maximum participant limit reached."
            ),
            403: OpenApiResponse(
                description="Forbidden – only moderators can add participants."
            ),
        },
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"], url_path="add_participant")
    def add_participant(self, request, pk=None):
        """Add participant to group"""
        try:
            group = self.get_object()

            # Validate moderator permission
            if not group.moderators.filter(id=request.user.id).exists():
                return Response(
                    {"error": "Only moderators can add participants"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
                )

            user = get_object_or_404(get_user_model(), id=user_id)

            if (
                group.participants.count()
                >= settings.GROUP_SETTINGS["MAX_PARTICIPANTS_PER_GROUP"]
            ):
                return Response(
                    {"error": "Maximum participant limit reached"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if user is already a participant
            if group.participants.filter(id=user_id).exists():
                return Response(
                    {"message": f"{user.username} is already a member of this group"},
                    status=status.HTTP_200_OK,
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

    @extend_schema(
        description="Remove a participant from the group.",
        summary="Remove Participant",
        request={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "ID of the user to remove from the group.",
                }
            },
            "required": ["user_id"],
        },
        responses={
            200: OpenApiResponse(description="User removed from group successfully."),
            403: OpenApiResponse(description="Forbidden – insufficient permission."),
            500: OpenApiResponse(description="Internal server error."),
        },
        tags=["Group Conversation"],
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

    @extend_schema(
        description="Pin a message in the group conversation.",
        summary="Pin Message",
        request={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "integer",
                    "description": "ID of the message to be pinned.",
                }
            },
            "required": ["message_id"],
        },
        responses={
            200: OpenApiResponse(description="Message pinned successfully."),
            400: OpenApiResponse(description="Bad Request – message_id missing."),
            403: OpenApiResponse(
                description="Forbidden – only moderators can pin messages."
            ),
        },
        tags=["Group Conversation"],
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
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        """Cache the group conversation list"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get group conversation with cache handling"""
        conversation_id = kwargs.get("pk")
        cache_key = f"group_conversation_{conversation_id}"

        # Try to get from cache first
        cached_conversation = cache.get(cache_key)
        if cached_conversation:
            return Response(cached_conversation)

        response = super().retrieve(request, *args, **kwargs)

        # Cache the response for 30 minutes (groups change more often than 1-1 chats)
        cache.set(cache_key, response.data, timeout=1800)
        return response

    @action(detail=False, methods=["get"], url_path="search_messages")
    def search_messages(self, request):
        """Search group messages by content with partial matching."""
        query = request.query_params.get("query", "").strip()
        if not query:
            return Response(
                {"error": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        messages = GroupMessage.objects.filter(content__icontains=query)
        serializer = GroupMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="search_groups")
    def search_groups(self, request):
        """Search group conversations by name with partial matching."""
        query = request.query_params.get("query", "").strip()
        if not query:
            return Response(
                {"error": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        groups = GroupConversation.objects.filter(name__icontains=query)
        serializer = GroupConversationSerializer(groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="search_all")
    def search_all(self, request):
        """Unified search for group conversations and one-to-one conversations by name."""
        query = request.query_params.get("query", "").strip()
        if not query:
            return Response(
                {"error": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Search group conversations
        group_results = GroupConversation.objects.filter(name__icontains=query)
        group_serializer = GroupConversationSerializer(group_results, many=True)

        # Search one-to-one conversations
        from ..models.one_to_one import OneToOneConversation
        from ..serializers.one_to_one import OneToOneConversationSerializer

        one_to_one_results = OneToOneConversation.objects.filter(
            participants__username__icontains=query
        ).distinct()
        one_to_one_serializer = OneToOneConversationSerializer(
            one_to_one_results, many=True
        )

        return Response(
            {
                "groups": group_serializer.data,
                "one_to_one": one_to_one_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GroupMessageViewSet(ReactionMixin, EditHistoryMixin, viewsets.ModelViewSet):
    """
    API endpoints for Group Messages.

    Supports CRUD operations, edit history, and reactions.
    """

    serializer_class = GroupMessageSerializer
    permission_classes = [IsParticipantOrModerator]
    throttle_classes = [GroupMessageThrottle]

    def get_queryset(self):
        """Filter messages to include only those in groups the user participates in."""
        user = self.request.user
        return GroupMessage.objects.filter(conversation__participants=user).order_by(
            "-timestamp"
        )

    def perform_create(self, serializer):
        """Set authenticated user as sender"""
        serializer.save(sender=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """Mark a message as read by the current user."""
        try:
            message = self.get_object()
            message.read_by.add(request.user)

            # Send read receipt via WebSocket
            conversation_id = str(message.conversation.id)
            from messaging.services.message_delivery import message_delivery_service

            message_delivery_service.send_read_receipt(
                conversation_id=conversation_id,
                user_id=str(request.user.id),
                username=request.user.username,
                message_id=str(message.id),
            )

            return Response({"status": "marked as read"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}")
            return Response(
                {"error": f"Failed to mark message as read: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
