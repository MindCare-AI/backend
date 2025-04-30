# messaging/views/chatbot.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from django.db import transaction
from ..models.chatbot import ChatbotConversation, ChatbotMessage
from ..serializers.chatbot import (
    ChatbotConversationSerializer,
    ChatbotMessageSerializer,
)
from ..services.chatbot import chatbot_service
import logging

logger = logging.getLogger(__name__)


class ChatbotThrottle(UserRateThrottle):
    rate = "30/minute"
    scope = "chatbot"


class ChatbotConversationViewSet(viewsets.ModelViewSet):
    queryset = ChatbotConversation.objects.all()
    serializer_class = ChatbotConversationSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ChatbotThrottle]

    def perform_create(self, serializer):
        """Ensure the authenticated user is set as the conversation user"""
        user = self.request.user
        existing = ChatbotConversation.objects.filter(user=user).first()
        if existing:
            # Optionally, you can return or raise a custom message.
            return existing
        serializer.save(user=user)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """Send a message in a chatbot conversation"""
        try:
            conversation = self.get_object()
            message_content = request.data.get("message")

            if not message_content:
                return Response(
                    {"error": "Message content is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get conversation history
            history = list(
                conversation.messages.order_by("-timestamp")[:5].values(
                    "content", "is_bot"
                )
            )

            # Get response from chatbot service (includes both Gemini and Ollama)
            response = chatbot_service.get_response(
                user=request.user, message=message_content, conversation_history=history
            )

            if not response.get("success"):
                return Response(
                    {"error": response.get("error", "Failed to get response")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Save user message and bot response in transaction
            with transaction.atomic():
                # Save user message
                user_message = ChatbotMessage.objects.create(
                    conversation=conversation,
                    content=message_content,
                    sender=request.user,
                    is_bot=False,
                )

                # Save bot response
                bot_message = ChatbotMessage.objects.create(
                    conversation=conversation, content=response["response"], is_bot=True
                )

            # Serialize messages
            message_serializer = ChatbotMessageSerializer()
            return Response(
                {
                    "user_message": message_serializer.to_representation(user_message),
                    "bot_message": message_serializer.to_representation(bot_message),
                    "context_used": response.get("context_used", {}),
                    "analysis": response.get("analysis", {}),
                }
            )

        except Exception as e:
            logger.error(f"Error in chatbot message: {str(e)}")
            return Response(
                {"error": "An error occurred processing your message"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
