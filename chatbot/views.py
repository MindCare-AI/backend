from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ChatbotConversation, ChatbotMessage
from .serializers import ChatbotConversationSerializer, ChatbotMessageSerializer
from .services.chatbot_service import chatbot_service
import logging

logger = logging.getLogger(__name__)


class ChatbotConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ChatbotConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatbotConversation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """Send a message to the chatbot and get a response"""
        try:
            conversation = self.get_object()
            
            # Validate message content
            serializer = ChatbotMessageSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Get recent conversation history - fixed the order of operations
            history = list(
                conversation.messages.order_by("timestamp")  # Order by timestamp ascending
                .values("content", "is_bot")
                .reverse()[:10]  # Then reverse and take last 10
            )

            # Save user message
            user_message = ChatbotMessage.objects.create(
                conversation=conversation,
                content=serializer.validated_data["content"],
                sender=request.user,
                is_bot=False
            )

            # Get chatbot response
            bot_response = chatbot_service.get_response(
                request.user,
                serializer.validated_data["content"],
                history
            )

            # Save bot response
            bot_message = ChatbotMessage.objects.create(
                conversation=conversation,
                content=bot_response["content"],
                is_bot=True
            )

            # Return both messages
            return Response(
                {
                    "user_message": ChatbotMessageSerializer(user_message).data,
                    "bot_response": ChatbotMessageSerializer(bot_message).data
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            return Response(
                {"error": "Failed to process message"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
