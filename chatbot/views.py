# chatbot/views.py
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from datetime import timedelta
from drf_spectacular.utils import extend_schema

from .models import ChatbotConversation, ChatMessage
from .serializers import ChatMessageSerializer, ChatbotConversationSerializer
from .services.chatbot_service import chatbot_service

logger = logging.getLogger(__name__)


class ChatbotPagination(PageNumberPagination):
    """Custom pagination for chatbot conversations"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ChatbotViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chatbot conversations and messages."""

    queryset = ChatbotConversation.objects.all()
    serializer_class = ChatbotConversationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatbotPagination

    def get_queryset(self):
        """Filter queryset to show only user's conversations from last 24 hours"""
        now = timezone.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        return ChatbotConversation.objects.filter(
            user=self.request.user, last_activity__gte=twenty_four_hours_ago
        ).order_by("-last_activity")

    def list(self, request, *args, **kwargs):
        """List conversations with their most recent messages"""
        queryset = self.get_queryset()

        # When user opens the chatbot screen for the first time,
        # auto-create a welcome conversation with an introduction message.
        if not queryset.exists():
            conversation = ChatbotConversation.objects.create(
                user=request.user, title="welcome", metadata={}
            )
            welcome_text = (
                "Welcome to your personal chatbot companion! We're delighted to have you here. "
                "At our service, we strive to create an engaging and uniquely tailored experience. "
                "To be of the utmost help, we discreetly collect information such as your conversation history, "
                "interaction patterns, and usage details. This data is guarded under the strictest confidentiality "
                "protocols and is treated as top secret—ensuring your privacy is never compromised. "
                "We use these insights solely to enhance your experience and provide you with exceptional support. "
                "Feel completely at ease; our commitment to your privacy and security stands paramount as you explore our features."
            )
            ChatMessage.objects.create(
                conversation=conversation,
                content=welcome_text,
                is_bot=True,
                message_type="system",
            )
            queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            for conversation in serializer.data:
                # Get the last 5 messages for each conversation
                messages = ChatMessage.objects.filter(
                    conversation_id=str(conversation["id"])
                ).order_by("-timestamp")[:5]
                conversation["recent_messages"] = ChatMessageSerializer(
                    messages, many=True
                ).data
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        description="Send a message to the chatbot and get a response",
        methods=["POST"],
        request=ChatMessageSerializer,
        responses={201: ChatMessageSerializer},
    )
    @action(detail=True, methods=["POST"], url_path="send_message")
    def send_message(self, request, pk=None):
        """Send a message to the chatbot and get a response."""
        try:
            conversation = self.get_object()

            # Check if the conversation belongs to the current user
            if conversation.user != request.user:
                return Response(
                    {"error": "You do not have access to this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get the content directly from request data
            content = request.data.get("content")
            if not content:
                return Response(
                    {"error": "Message content is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate and create the user's message
            message_data = {
                "content": content,
                "conversation": conversation.id,
                "sender": request.user.id,
                "is_bot": False,
            }

            message_serializer = ChatMessageSerializer(data=message_data)
            if not message_serializer.is_valid():
                return Response(
                    message_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

            # Attach conversation FK explicitly
            user_message = message_serializer.save(conversation=conversation)

            # Get conversation history
            conversation_messages = ChatMessage.objects.filter(
                conversation=conversation
            ).order_by("timestamp")

            # Get chatbot response
            bot_response = chatbot_service.get_response(
                user=request.user,
                message=user_message.content,
                conversation_id=str(conversation.id),
                conversation_history=[
                    {
                        "id": msg.id,
                        "content": msg.content,
                        "is_bot": msg.is_bot,
                        "timestamp": msg.timestamp,
                    }
                    for msg in conversation_messages
                ],
            )

            # Create bot's response message
            bot_message_data = {
                "content": bot_response["content"],
                "conversation": conversation.id,
                "sender": None,
                "is_bot": True,
            }

            bot_message_serializer = ChatMessageSerializer(data=bot_message_data)
            if not bot_message_serializer.is_valid():
                return Response(
                    bot_message_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

            bot_message = bot_message_serializer.save(conversation=conversation)

            # Update conversation's last activity
            conversation.last_activity = timezone.now()
            conversation.save()

            # Return both user message and bot response with complete serialized data
            return Response(
                {
                    "user_message": ChatMessageSerializer(user_message).data,
                    "bot_response": ChatMessageSerializer(bot_message).data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error in chatbot message handling: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to process message"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
