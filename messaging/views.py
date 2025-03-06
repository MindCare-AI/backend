# messaging/views.py
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model
from .chatbot.chatbot import get_ollama_response  # Import the chatbot function directly
from messaging.firebase_client import push_message  # New import

from .models import Conversation, Message, Reaction, ConversationType
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    GroupChatSerializer,
    ReactionSerializer,
    GroupManagementSerializer,
)


# Pagination class for conversations
class ConversationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema_view(
    get=extend_schema(
        summary="List user conversations",
        description="Retrieve a paginated list of active conversations for the authenticated user.",
    ),
    post=extend_schema(
        summary="Create conversation",
        description="Create a new conversation (direct, chatbot, or group) based on the provided data.",
    ),
)
class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    pagination_class = ConversationPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.conversations.filter(is_active=True)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        conversation_type = request.data.get("conversation_type", "direct")
        valid_types = [choice[0] for choice in ConversationType.choices]
        if conversation_type not in valid_types:
            return Response(
                {
                    "conversation_type": f'Invalid conversation type. Must be one of: {", ".join(valid_types)}'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Direct conversation
        if conversation_type == "direct":
            participants = request.data.get("participants", [])
            # We need to ensure there is exactly one participant (the other user)
            if not participants or len(participants) != 1:
                return Response(
                    {
                        "participants": "Direct messages require exactly one participant (excluding yourself)."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Validate the other user exists
            other_user = get_object_or_404(get_user_model(), id=participants[0])
            
            # Check if a direct conversation between the two users already exists
            existing_conversation = (
                Conversation.objects.filter(
                    conversation_type="direct", participants=self.request.user
                )
                .filter(participants=other_user)
                .first()
            )
            if existing_conversation:
                serializer = self.get_serializer(existing_conversation)
                return Response(serializer.data, status=status.HTTP_200_OK)
            
            # Keep participant as is - the serializer will handle adding the current user
            # No need to modify request.data["participants"] here

        # Chatbot conversation
        elif conversation_type == "chatbot":
            # Check for existing chatbot conversation
            existing_chat = Conversation.objects.filter(
                participants=request.user, conversation_type="chatbot"
            ).first()
            if existing_chat:
                serializer = self.get_serializer(existing_chat)
                return Response(serializer.data, status=status.HTTP_200_OK)
            
            # For chatbot, we don't need additional participants
            request.data["participants"] = []  # Empty list, serializer will add current user

        # Group conversation: validate participant IDs and ensure creator is included
        elif conversation_type == "group":
            # Group chat logic remains the same
            participants = request.data.get("participants", [])
            if not isinstance(participants, list):
                participants = []
            # Validate that each provided participant exists
            valid_participants = []
            User = get_user_model()
            for user_id in participants:
                if User.objects.filter(id=user_id).exists():
                    valid_participants.append(user_id)
            
            # No need to add current user here, serializer will handle it
            # Remove duplicates while preserving order
            request.data["participants"] = list(dict.fromkeys(valid_participants))

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        conversation_type = self.request.data.get("conversation_type", "direct")
        conversation = serializer.save(conversation_type=conversation_type)
        if conversation_type == "group":
            conversation.moderators.add(self.request.user)
        return conversation


@extend_schema_view(
    post=extend_schema(
        summary="Create group conversation",
        description="Create a new group conversation for the authenticated user with validated participants.",
    )
)
class GroupChatCreateView(generics.CreateAPIView):
    serializer_class = GroupChatSerializer
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # Validate participant IDs
        participants = request.data.get("participants", [])
        if not isinstance(participants, list):
            participants = []
        User = get_user_model()
        valid_participants = []
        for user_id in participants:
            if User.objects.filter(id=user_id).exists():
                valid_participants.append(user_id)
        if request.user.id not in valid_participants:
            valid_participants.append(request.user.id)
        request.data["participants"] = list(dict.fromkeys(valid_participants))
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        conversation = serializer.save(conversation_type="group")
        conversation.moderators.add(self.request.user)
        return conversation


@extend_schema(
    summary="Chatbot conversation",
    description="Initialize a chatbot conversation. If one exists, return it; otherwise, create a new chatbot conversation.",
    responses={200: ConversationSerializer, 201: ConversationSerializer},
)
class ChatbotConversationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Check if user already has a chatbot conversation
        existing_chat = Conversation.objects.filter(
            participants=request.user, conversation_type="chatbot"
        ).first()

        if existing_chat:
            serializer = ConversationSerializer(existing_chat)
            return Response(
                {
                    "conversation_id": existing_chat.id,
                    "message": "Continuing existing chatbot conversation",
                    "conversation": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        # Create new chatbot conversation
        conversation = Conversation.objects.create(conversation_type="chatbot")
        conversation.participants.add(request.user)
        serializer = ConversationSerializer(conversation)
        return Response(
            {
                "conversation_id": conversation.id,
                "message": "Started new chatbot conversation",
                "conversation": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        summary="List messages",
        description="Retrieve a list of messages for a given conversation."
    ),
    post=extend_schema(
        summary="Create message",
        description="Create a new message. For chatbot conversations, returns both the user message and the chatbot response."
    )
)
class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs.get("conversation_id")
        try:
            return (
                Message.objects.filter(
                    conversation_id=conversation_id,
                    conversation__participants=self.request.user,
                )
                .select_related("sender", "conversation")
                .order_by("-timestamp")
            )
        except Exception:
            raise NotFound("Conversation not found or access denied")

    @transaction.atomic
    def perform_create(self, serializer):
        conversation_id = self.kwargs.get("conversation_id")
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=self.request.user,
            is_active=True,
        )

        message = serializer.save(sender=self.request.user, conversation=conversation)

        # For non-chatbot conversations, push the new message to Firebase.
        if conversation.conversation_type != "chatbot":
            firebase_data = {
                "message": message.content,
                "sender": self.request.user.username,
                "timestamp": str(message.timestamp),
                "message_id": message.id,
            }
            push_message(conversation_id, firebase_data)

        # For chatbot conversations, the bot response is handled in perform_create below.
        if conversation.conversation_type == "chatbot":
            try:
                history = list(
                    Message.objects.filter(conversation=conversation)
                    .order_by("-timestamp")[:3]
                    .values("content", "is_chatbot")
                )

                formatted_history = [
                    {
                        "content": msg["content"],
                        "role": "user" if not msg["is_chatbot"] else "assistant",
                    }
                    for msg in reversed(history)
                ]

                chatbot_response = get_ollama_response(message.content, formatted_history)
                bot_message = Message.objects.create(
                    conversation=conversation,
                    sender=self.request.user,  # Alternatively, assign a bot user here
                    content=chatbot_response,
                    is_chatbot=True,
                    message_type="text"
                )
                # Push bot message to Firebase
                firebase_bot_data = {
                    "message": chatbot_response,
                    "sender": "Samantha",
                    "timestamp": str(bot_message.timestamp),
                    "message_id": bot_message.id,
                }
                push_message(conversation_id, firebase_bot_data)

                return [message, bot_message]
            except Exception as e:
                # Log the error and handle the failure as needed.
                bot_message = Message.objects.create(
                    conversation=conversation,
                    sender=self.request.user,
                    content="Sorry, I encountered an error processing your request.",
                    is_chatbot=True,
                    message_type="system"
                )
                firebase_error_data = {
                    "message": bot_message.content,
                    "sender": "Samantha",
                    "timestamp": str(bot_message.timestamp),
                    "message_id": bot_message.id,
                }
                push_message(conversation_id, firebase_error_data)
                return [message, bot_message]

        return message

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Override create to handle both user message and chatbot response consistently"""
        # Get the conversation first
        conversation_id = self.kwargs.get("conversation_id")
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=self.request.user,
            is_active=True,
        )

        # Create the user's message
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_message = self.perform_create(serializer)

        # For chatbot conversations, return both messages
        if conversation.conversation_type == "chatbot":
            # Get both the user message and the bot response that was created in perform_create
            latest_messages = Message.objects.filter(
                conversation=conversation
            ).order_by("-timestamp")[:2]
            
            response_serializer = self.get_serializer(latest_messages, many=True)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )

        # For regular conversations, return just the user message
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    get=extend_schema(summary="Retrieve message"),
    patch=extend_schema(summary="Update message"),
    put=extend_schema(summary="Update message"),
    delete=extend_schema(summary="Delete message")
)
class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    New endpoint: allows editing and deletion (or soft deletion) of a message.
    """

    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(
            conversation__participants=self.request.user
        ).select_related("sender", "conversation")

    def perform_update(self, serializer):
        message = self.get_object()
        # Only the sender should be allowed to update their message.
        if message.sender != self.request.user:
            raise PermissionDenied("You are not allowed to edit this message.")
        serializer.save()

    def perform_destroy(self, instance):
        # Here you could perform a soft delete (e.g. mark as deleted) instead of hard deletion.
        # For demonstration, we are doing a hard delete.
        if instance.sender != self.request.user:
            raise PermissionDenied("You are not allowed to delete this message.")
        instance.delete()


@extend_schema(
    summary="Toggle reaction on message",
    description="Add or toggle a reaction on a given message.",
    responses={201: ReactionSerializer, 204: None}
)
class MessageReactionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, message_id):
        """Add/toggle reaction on a message"""
        message = get_object_or_404(
            Message.objects.filter(conversation__participants=request.user),
            id=message_id,
        )

        emoji = request.data.get("emoji")
        if not emoji:
            return Response(
                {"error": "Emoji is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        reaction, created = Reaction.objects.get_or_create(
            message=message, user=request.user, emoji=emoji
        )

        if not created:
            reaction.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            ReactionSerializer(reaction).data, status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    get=extend_schema(
        summary="Search messages",
        description="Search for messages by content or sender username, optionally within a specific conversation."
    )
)
class MessageSearchView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get("query", "").strip()
        conversation_id = self.request.query_params.get("conversation")

        if not query:
            return Message.objects.none()

        queryset = Message.objects.filter(
            conversation__participants=self.request.user
        ).select_related("sender", "conversation")

        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)

        return queryset.filter(
            Q(content__icontains=query) | Q(sender__username__icontains=query)
        )


@extend_schema(
    summary="Manage group conversation",
    description="Perform group management actions such as adding or removing moderators/users.",
)
class GroupManagementView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GroupManagementSerializer

    def _check_moderator_permission(self, conversation):
        if self.request.user not in conversation.moderators.all():
            raise PermissionDenied("Only moderators can perform this action")

    def post(self, request, group_id):
        """Handle group management actions"""
        conversation = get_object_or_404(
            Conversation.objects.filter(conversation_type="group"), id=group_id
        )

        self._check_moderator_permission(conversation)

        action = request.query_params.get("action")
        user_id = request.data.get("user_id")

        if not user_id:
            return Response(
                {"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        target_user = get_object_or_404(get_user_model(), id=user_id)

        actions = {
            "add-moderator": lambda: conversation.moderators.add(target_user),
            "remove-moderator": lambda: conversation.moderators.remove(target_user),
            "invite-user": lambda: conversation.participants.add(target_user),
            "remove-user": lambda: conversation.participants.remove(target_user),
        }

        if action not in actions:
            return Response(
                {
                    "error": f'Invalid action. Must be one of: {", ".join(actions.keys())}'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            actions[action]()
            return Response({"message": f"Successfully performed {action}"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(summary="Retrieve conversation"),
    patch=extend_schema(summary="Update conversation"),
    put=extend_schema(summary="Update conversation"),
    delete=extend_schema(summary="Delete conversation (soft delete)")
)
class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user, is_active=True
        )

    def perform_update(self, serializer):
        conversation = self.get_object()
        if self.request.user not in conversation.moderators.all():
            raise PermissionDenied("Only moderators can update the conversation")
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user not in instance.moderators.all():
            raise PermissionDenied("Only moderators can delete the conversation")
        # Soft-delete the conversation by marking it inactive.
        instance.is_active = False
        instance.save()


@extend_schema(
    summary="Mark message as read",
    description="Mark the specified message as read.",
    responses={200: {"message": "Message marked as read"}}
)
class MessageMarkAsReadView(APIView):
    """
    New endpoint: Marks a message as read.
    (This assumes you have a field or mechanism on the Message model to track read status.)
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, message_id):
        message = get_object_or_404(
            Message.objects.filter(conversation__participants=request.user),
            id=message_id,
        )
        # Example: Assume Message model has an `is_read` boolean field.
        # In a real implementation, you might track per-user read receipts.
        if not getattr(message, "is_read", False):
            message.is_read = True
            message.save()
        return Response(
            {"message": "Message marked as read"}, status=status.HTTP_200_OK
        )
