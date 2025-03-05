# messaging/views.py
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

from .models import Conversation, Message, Reaction
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


class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    pagination_class = ConversationPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.conversations.filter(is_active=True)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        conversation_type = request.data.get("conversation_type", "direct")
        valid_types = dict(Conversation.CONVERSATION_TYPES).keys()
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
            if not participants or len(participants) != 1:
                return Response(
                    {
                        "participants": "Direct messages require exactly one participant (excluding yourself)."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Validate the other user exists
            other_user = get_object_or_404(get_user_model(), id=participants[0])
            # Check if a direct conversation between the two users already exists.
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
            # Set participants list as IDs of current user and other user.
            request.data["participants"] = [self.request.user.id, other_user.id]

        # Chatbot conversation
        elif conversation_type == "chatbot":
            existing_chat = Conversation.objects.filter(
                participants=request.user, conversation_type="chatbot"
            ).first()
            if existing_chat:
                serializer = self.get_serializer(existing_chat)
                return Response(serializer.data, status=status.HTTP_200_OK)
            # For chatbot, we only add the current user.
            request.data["participants"] = [self.request.user.id]

        # Group conversation: validate participant IDs and ensure creator is included.
        elif conversation_type == "group":
            participants = request.data.get("participants", [])
            if not isinstance(participants, list):
                participants = []
            # Validate that each provided participant exists.
            valid_participants = []
            User = get_user_model()
            for user_id in participants:
                if User.objects.filter(id=user_id).exists():
                    valid_participants.append(user_id)
            if self.request.user.id not in valid_participants:
                valid_participants.append(self.request.user.id)
            # Remove duplicates while preserving order
            request.data["participants"] = list(dict.fromkeys(valid_participants))

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        conversation_type = self.request.data.get("conversation_type", "direct")
        conversation = serializer.save(conversation_type=conversation_type)
        if conversation_type == "group":
            conversation.moderators.add(self.request.user)
        return conversation


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

        # If this is a chatbot conversation, handle the response immediately
        if conversation.conversation_type == "chatbot":
            try:
                # Get conversation history
                history = list(
                    Message.objects.filter(conversation=conversation)
                    .order_by("-timestamp")[:3]
                    .values("content", "is_chatbot")
                )

                # Format history in the way get_ollama_response expects
                formatted_history = [
                    {
                        "content": msg["content"],
                        "response": "User response"
                        if msg["is_chatbot"]
                        else "Bot response",
                    }
                    for msg in history
                ]

                # Get chatbot response
                chatbot_response = get_ollama_response(
                    message.content, formatted_history
                )

                # Create chatbot response message
                bot_message = Message.objects.create(
                    conversation=conversation,
                    sender=self.request.user,  # Using the same user for now
                    content=chatbot_response,
                    is_chatbot=True,
                    message_type="text",
                )

            except Exception as e:
                # Handle errors by creating a system message
                print(f"Error generating chatbot response: {str(e)}")
                bot_message = Message.objects.create(
                    conversation=conversation,
                    sender=self.request.user,
                    content="Sorry, the chatbot service is currently unavailable. Please try again later.",
                    is_chatbot=True,
                    message_type="system",
                )

        return message

    def create(self, request, *args, **kwargs):
        """Override create to return both the user message and chatbot response"""
        response = super().create(request, *args, **kwargs)

        # If this was a successful message creation in a chatbot conversation
        conversation_id = self.kwargs.get("conversation_id")
        if response.status_code == status.HTTP_201_CREATED:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id, conversation_type="chatbot", is_active=True
                )

                # Get the last two messages (user message and chatbot response)
                latest_messages = Message.objects.filter(
                    conversation=conversation
                ).order_by("-timestamp")[:2]

                # Serialize the messages
                serializer = self.get_serializer(latest_messages, many=True)
                response.data = serializer.data
            except Conversation.DoesNotExist:
                # Not a chatbot conversation, return the original response
                pass

        return response


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
