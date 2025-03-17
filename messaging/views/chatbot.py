# messaging/views/chatbot.py
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)  # Used to enhance the auto-generated Swagger docs.
from ..models.chatbot import ChatbotConversation, ChatbotMessage
from ..serializers.chatbot import (
    ChatbotConversationSerializer,
    ChatbotMessageSerializer,
)
from ..permissions import IsPatient
from ..throttling import ChatbotRateThrottle
from ..pagination import CustomMessagePagination
from ..services.chatbot import chatbot_service
import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="Return all chatbot conversations for the authenticated patient.",
        summary="List Chatbot Conversations",
        tags=["Chatbot"],
    ),
    retrieve=extend_schema(
        description="Retrieve a specific chatbot conversation details.",
        summary="Retrieve Chatbot Conversation",
        tags=["Chatbot"],
    ),
    create=extend_schema(
        description="Create or retrieve the existing chatbot conversation for the authenticated patient.",
        summary="Create Chatbot Conversation",
        tags=["Chatbot"],
    ),
)
class ChatbotConversationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsPatient]
    serializer_class = ChatbotConversationSerializer
    pagination_class = CustomMessagePagination
    throttle_classes = [ChatbotRateThrottle]

    def get_queryset(self):
        return ChatbotConversation.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        conv, created = ChatbotConversation.objects.get_or_create(user=request.user)
        return Response(
            self.get_serializer(conv).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        description="Send a message to the chatbot",
        request=ChatbotMessageSerializer,
        responses={201: ChatbotMessageSerializer},
    )
    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """
        Send a message to the chatbot and get response using ChatbotService.
        """
        conversation = self.get_object()

        try:
            # Validate and save user message
            serializer = ChatbotMessageSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Invalid message data: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Save user message
            user_message = serializer.save(
                sender=request.user, conversation=conversation, is_bot=False
            )
            logger.debug(f"Saved user message: {user_message.id}")

            # Get conversation history
            history = list(
                conversation.messages.order_by("-timestamp").values(
                    "sender", "content", "is_bot"
                )[:5]
            )
            history.reverse()

            # Get bot response using ChatbotService
            try:
                bot_response = chatbot_service.get_response(
                    message=serializer.validated_data["content"],
                    history=[{
                        "content": msg["content"],
                        "is_bot": msg["is_bot"]
                    } for msg in history]
                )
                
                if not bot_response["success"]:
                    logger.error(f"Chatbot service error: {bot_response.get('error')}")
                    return Response(
                        {"error": bot_response["response"]},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
                
                response_content = bot_response["response"]
                logger.debug(f"Got bot response: {response_content[:50]}...")
                
            except Exception as e:
                logger.error(f"Error getting bot response: {str(e)}")
                response_content = "I apologize, but I'm having trouble processing your request."

            # Save bot response
            bot_message = ChatbotMessage.objects.create(
                conversation=conversation,
                content=response_content,
                is_bot=True
            )
            logger.debug(f"Saved bot message: {bot_message.id}")

            return Response(
                {
                    "user_message": ChatbotMessageSerializer(user_message).data,
                    "bot_response": ChatbotMessageSerializer(bot_message).data,
                },
                status=status.HTTP_201_CREATED,
            )

        except ChatbotConversation.DoesNotExist:
            logger.error(f"Conversation {pk} not found")
            return Response(
                {"error": "Conversation not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Unexpected error in send_message: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
