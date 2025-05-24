# messaging/views/one_to_one.py
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Count, Max, Q, Prefetch
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
    OpenApiResponse,
)

from ..models.one_to_one import OneToOneConversation, OneToOneMessage
from ..serializers.one_to_one import (
    OneToOneConversationSerializer,
    OneToOneMessageSerializer,
)

# New corrected import
# Removed Firebase import
# from ..services.firebase import push_message  # DELETE THIS LINE
import logging
from ..mixins.edit_history import EditHistoryMixin
from ..mixins.reactions import ReactionMixin
from django.db import transaction

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all one-to-one conversations for the authenticated user.",
        summary="List One-to-One Conversations",
        tags=["One-to-One Conversation"],
    ),
    retrieve=extend_schema(
        description="Retrieve detailed information for a specific one-to-one conversation.",
        summary="Retrieve One-to-One Conversation",
        tags=["One-to-One Conversation"],
    ),
    create=extend_schema(
        description="Create a new one-to-one conversation. Expects a request body with a 'participant_id'.",
        summary="Create One-to-One Conversation",
        request={
            "type": "object",
            "properties": {
                "participant_id": {
                    "type": "integer",
                    "description": "ID of the second participant (must be a patient if you're a therapist, or vice versa).",
                }
            },
            "required": ["participant_id"],
        },
        responses={
            201: OneToOneConversationSerializer,
            400: OpenApiResponse(
                description="Bad Request – e.g., missing or invalid participant_id."
            ),
            404: OpenApiResponse(description="Participant not found."),
        },
        examples=[
            OpenApiExample(
                "Valid Request",
                description="A valid request to create a one-to-one conversation.",
                value={"participant_id": 2},
            )
        ],
        tags=["One-to-One Conversation"],
    ),
)
class OneToOneConversationViewSet(viewsets.ModelViewSet):
    queryset = OneToOneConversation.objects.all()
    serializer_class = OneToOneConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Get conversations that the current user is part of,
        with annotations for latest message info and unread count.
        """
        user = self.request.user

        # Prefetch recent messages for each conversation to avoid N+1 queries.
        message_prefetch = Prefetch(
            "messages",
            queryset=OneToOneMessage.objects.order_by("-timestamp"),
            to_attr="all_messages",
        )

        # Get all conversations with additional useful data.
        return (
            self.queryset.filter(participants=user)
            .prefetch_related("participants", message_prefetch)
            .annotate(
                last_message_time=Max("messages__timestamp"),
                unread_count=Count(
                    "messages",
                    filter=~Q(messages__read_by=user) & ~Q(messages__sender=user),
                ),
            )
            .order_by("-last_message_time")
        )

    @extend_schema(
        description="Enhanced list response that returns conversation data enriched with latest message preview and unread message counts. Supports pagination.",
        summary="Enhanced List One-to-One Conversations",
        tags=["One-to-One Conversation"],
    )
    def list(self, request, *args, **kwargs):
        """Enhanced list response with additional data."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                response_data = self.enrich_conversation_data(serializer.data)
                return self.get_paginated_response(response_data)
            serializer = self.get_serializer(queryset, many=True)
            response_data = self.enrich_conversation_data(serializer.data)
            return Response(response_data)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Enhanced detail view for a one-to-one conversation including participant info and recent message history. Also marks unread messages as read.",
        summary="Enhanced Retrieve One-to-One Conversation",
        tags=["One-to-One Conversation"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Enhanced detail view with messages."""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            response_data = serializer.data

            # Add other participant information
            other_participants = instance.participants.exclude(id=request.user.id)
            response_data["other_participants"] = [
                {
                    "id": participant.id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                    "email": participant.email,
                }
                for participant in other_participants
            ]

            # Get recent messages (limit to last 20) and convert to list
            messages = list(instance.messages.all().order_by("-timestamp")[:20])
            message_serializer = OneToOneMessageSerializer(messages, many=True)
            response_data["messages"] = message_serializer.data

            # Mark messages as read using Python filtering on the list
            unread_messages = [
                message
                for message in messages
                if message.sender != request.user
                and request.user not in message.read_by.all()
            ]
            for message in unread_messages:
                message.read_by.add(request.user)

            return Response(response_data)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Retrieve messages for a specific conversation with support for cursor-based pagination using before and after parameters.",
        summary="List Conversation Messages",
        tags=["One-to-One Conversation"],
    )
    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, pk=None):
        """Get all messages for a conversation with proper pagination and consistent response format."""
        conversation = self.get_object()

        # Get messages in chronological order (oldest first)
        messages = OneToOneMessage.objects.filter(conversation=conversation).order_by(
            "timestamp"
        )

        # Apply pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = OneToOneMessageSerializer(
                page, many=True, context={"request": request}
            )
            response = self.get_paginated_response(serializer.data)
            return response

        # If pagination is not configured
        serializer = OneToOneMessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(
            {
                "results": serializer.data,
                "count": messages.count(),
            }
        )

    @extend_schema(
        description="Set the conversation status as 'typing' for the authenticated user.",
        summary="Set Typing Status",
        request=None,  # explicitly no body expected
        tags=["One-to-One Conversation"],
    )
    @action(detail=True, methods=["post"])
    def typing(self, request, pk=None):
        conversation = self.get_object()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"conversation_{conversation.id}",
            {
                "type": "typing.indicator",
                "user_id": str(request.user.id),
                "username": request.user.username,
                "conversation_id": str(conversation.id),
                "is_typing": True,
            },
        )
        return Response({"status": "typing"}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Search for messages within the conversation that contain a specified query string.",
        summary="Search Conversation Messages",
        tags=["One-to-One Conversation"],
    )
    @action(detail=True, methods=["get"])
    def search(self, request, pk=None):
        query = request.query_params.get("query")
        if not query:
            return Response(
                {"error": "Query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        messages = OneToOneMessage.objects.filter(
            content__icontains=query, conversation=pk
        )
        serializer = OneToOneMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def enrich_conversation_data(self, data):
        """Add additional information to conversation data for the UI."""
        user = self.request.user
        for conversation_data in data:
            conversation_id = conversation_data["id"]
            conversation = OneToOneConversation.objects.get(id=conversation_id)
            other_participants = conversation.participants.exclude(id=user.id)
            conversation_data["other_participants"] = [
                {
                    "id": participant.id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                    "email": participant.email,
                }
                for participant in other_participants
            ]
            # Slice the prefetched messages in Python
            latest_messages = getattr(conversation, "all_messages", [])[:5]
            if latest_messages:
                latest_message = latest_messages[0]
                conversation_data["latest_message"] = {
                    "id": latest_message.id,
                    "content": latest_message.content[:100]
                    + ("..." if len(latest_message.content) > 100 else ""),
                    "timestamp": latest_message.timestamp,
                    "is_from_current_user": latest_message.sender_id == user.id,
                    "sender_name": latest_message.sender.get_full_name()
                    or latest_message.sender.username,
                }
        return data

    def perform_create(self, serializer):
        user = self.request.user
        validated_participants = serializer.validated_data.get("participants", [])
        # Automatically include the authenticated user.
        validated_participants.append(user)
        serializer.save(participants=validated_participants)

    def create(self, request, *args, **kwargs):
        """
        Create a one-to-one conversation.
        Expects a payload with 'participant_id' for the second user.
        """
        other_participant_id = request.data.get("participant_id")
        if not other_participant_id:
            return Response(
                {"error": "Participant ID is required for one-to-one conversations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            User = get_user_model()
            other_participant = User.objects.get(id=other_participant_id)

            # First check if conversation already exists to avoid duplicates
            existing_conversation = (
                OneToOneConversation.objects.filter(participants=request.user)
                .filter(participants=other_participant)
                .first()
            )

            if existing_conversation:
                # Return existing conversation instead of creating a new one
                serializer = self.get_serializer(existing_conversation)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Validate user types if needed
            user_types = {request.user.user_type, other_participant.user_type}
            if user_types != {"patient", "therapist"}:
                return Response(
                    {"error": "Conversation must have one patient and one therapist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create new conversation with atomic transaction
            with transaction.atomic():
                conversation = OneToOneConversation.objects.create()
                conversation.participants.add(request.user, other_participant)

            serializer = self.get_serializer(conversation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response(
                {"error": "The specified participant does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to create conversation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OneToOneMessageViewSet(ReactionMixin, EditHistoryMixin, viewsets.ModelViewSet):
    queryset = OneToOneMessage.objects.all()
    serializer_class = OneToOneMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer]

    def get_queryset(self):
        """Filter messages to include only those in conversations the user participates in."""
        user = self.request.user
        return OneToOneMessage.objects.filter(conversation__participants=user).order_by(
            "timestamp"  # Changed from "-timestamp" to ascending order
        )

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        """Cache the message list for better performance"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get message with cache handling and debug logging."""
        message_id = kwargs.get("pk")
        logger.debug(f"Attempting to retrieve message with ID: {message_id}")

        # Check if the message exists in the queryset
        try:
            message = self.get_queryset().get(id=message_id)
            logger.debug(f"Message found: {message}")
        except OneToOneMessage.DoesNotExist:
            logger.error(
                f"Message with ID {message_id} does not exist or is not accessible."
            )
            return Response(
                {"detail": "No OneToOneMessage matches the given query."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Try to get from cache first
        cache_key = f"one_to_one_message_{message_id}"
        cached_message = cache.get(cache_key)
        if cached_message:
            logger.debug(f"Returning cached message for ID: {message_id}")
            return Response(cached_message)

        # Serialize and cache the response
        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=3600)
        return response

    def perform_create(self, serializer):
        """Handle media uploads during message creation."""
        request = self.request
        if not request.user:
            raise serializers.ValidationError("Authenticated user is required.")

        # Pass the authenticated user as the sender
        serializer.save(sender=request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = (
            self.request
        )  # Ensure the request is passed to the serializer
        return context

    def get_serializer(self, *args, **kwargs):
        """Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)
