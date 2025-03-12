# messaging/views/one_to_one.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from django.db.models import Count, Max, Q, Prefetch

# Import extend_schema and extend_schema_view to enrich Swagger/OpenAPI docs.
# • extend_schema: Adds detailed metadata (description, summary, tags, etc.) to a specific view method.
# • extend_schema_view: Applies common schema settings to all view methods of a viewset.
from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models.one_to_one import OneToOneConversation, OneToOneMessage
from ..serializers.one_to_one import (
    OneToOneConversationSerializer,
    OneToOneMessageSerializer,
)


@extend_schema_view(
    list=extend_schema(
        description="List all one-to-one conversations for the authenticated user. Each conversation includes annotations for the latest message, its time, unread count, and participant details.",
        summary="List One-to-One Conversations",
        tags=["One-to-One Conversation"],
    ),
    retrieve=extend_schema(
        description="Retrieve detailed information for a specific one-to-one conversation, including recent messages and details about the other participant(s).",
        summary="Retrieve One-to-One Conversation",
        tags=["One-to-One Conversation"],
    ),
    create=extend_schema(
        description="Create a new one-to-one conversation.",
        summary="Create One-to-One Conversation",
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
            queryset=OneToOneMessage.objects.order_by("-timestamp")[:5],
            to_attr="recent_messages",
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

            # Get recent messages (limit to last 20)
            messages = instance.messages.all().order_by("-timestamp")[:20]
            message_serializer = OneToOneMessageSerializer(messages, many=True)
            response_data["messages"] = message_serializer.data

            # Mark messages as read
            unread_messages = messages.exclude(sender=request.user).exclude(
                read_by=request.user
            )
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
    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        try:
            conversation = self.get_object()
            page_size = int(request.query_params.get("page_size", 20))
            before_id = request.query_params.get("before_id")
            after_id = request.query_params.get("after_id")

            messages = conversation.messages.all()
            if before_id:
                before_message = OneToOneMessage.objects.get(id=before_id)
                messages = messages.filter(timestamp__lt=before_message.timestamp)
            if after_id:
                after_message = OneToOneMessage.objects.get(id=after_id)
                messages = messages.filter(timestamp__gt=after_message.timestamp)
            messages = messages.order_by("-timestamp")[:page_size]
            serializer = OneToOneMessageSerializer(messages, many=True)

            unread_messages = messages.exclude(sender=request.user).exclude(
                read_by=request.user
            )
            for message in unread_messages:
                message.read_by.add(request.user)

            return Response(
                {"results": serializer.data, "has_more": messages.count() == page_size}
            )
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Set the conversation status as 'typing' for the authenticated user.",
        summary="Set Typing Status",
        tags=["One-to-One Conversation"],
    )
    @action(detail=True, methods=["post"])
    def typing(self, request, pk=None):
        conversation = self.get_object()
        conversation.is_typing = True
        conversation.save()
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
            latest_messages = getattr(conversation, "recent_messages", [])
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


@extend_schema_view(
    list=extend_schema(
        description="List all messages in one-to-one conversations for the authenticated user.",
        summary="List One-to-One Messages",
        tags=["One-to-One Message"],
    ),
    retrieve=extend_schema(
        description="Retrieve details of a specific one-to-one message.",
        summary="Retrieve One-to-One Message",
        tags=["One-to-One Message"],
    ),
)
class OneToOneMessageViewSet(viewsets.ModelViewSet):
    queryset = OneToOneMessage.objects.all()
    serializer_class = OneToOneMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(conversation__participants=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            conversation_id = serializer.validated_data.get("conversation")
            if conversation_id:
                try:
                    conversation = OneToOneConversation.objects.get(
                        id=conversation_id.id, participants=request.user
                    )
                except OneToOneConversation.DoesNotExist:
                    return Response(
                        {
                            "detail": "Conversation not found or you are not a participant."
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def perform_create(self, serializer):
        """Set the current user as the sender of the message."""
        try:
            serializer.save(sender=self.request.user)
        except IntegrityError as e:
            raise ValidationError(f"Failed to create message: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")

    def update(self, request, *args, **kwargs):
        """Allow message update only by the sender."""
        try:
            instance = self.get_object()
            if instance.sender != request.user:
                return Response(
                    {"detail": "You can only edit messages you've sent."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return super().update(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def perform_update(self, serializer):
        """Prevent changing the sender."""
        try:
            serializer.save(sender=serializer.instance.sender)
        except IntegrityError as e:
            raise ValidationError(f"Failed to update message: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")
