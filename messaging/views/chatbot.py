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
from ..tasks import process_chatbot_response
from ..throttling import ChatbotRateThrottle
from ..pagination import CustomMessagePagination
import logging

logger = logging.getLogger(__name__)


def get_chatbot_response(message, history):
    """
    Get chatbot response with error handling and logging.
    """
    try:
        logger.debug(f"Processing message: {message}")
        logger.debug(f"History length: {len(history)}")
        
        # For immediate testing, return a static response
        return "I'm here to help. How are you feeling today?"
        
        # TODO: Uncomment after testing
        # return process_chatbot_response(message, history)
    except Exception as e:
        logger.error(f"Error getting chatbot response: {str(e)}")
        return "I apologize, but I'm having trouble processing your message."


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
        responses={202: ChatbotMessageSerializer},
    )
    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """
        Send a message to the chatbot and get response.
        """
        conversation = self.get_object()
        
        try:
            # Validate and save user message
            serializer = ChatbotMessageSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Invalid message data: {serializer.errors}")
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Save user message
            user_message = serializer.save(
                sender=request.user,
                conversation=conversation,
                is_bot=False
            )
            logger.debug(f"Saved user message: {user_message.id}")

            # Get conversation history
            history = list(
                conversation.messages
                .order_by('-timestamp')
                .values('sender', 'content')[:5]
            )
            history.reverse()

            # Get bot response
            try:
                bot_response = get_chatbot_response(
                    message=serializer.validated_data['content'],
                    history=history
                )
                logger.debug(f"Got bot response: {bot_response[:50]}...")
            except Exception as e:
                logger.error(f"Error getting bot response: {str(e)}")
                bot_response = "I apologize, but I'm having trouble processing your request."

            # Save bot response
            bot_message = ChatbotMessage.objects.create(
                conversation=conversation,
                content=bot_response,
                is_bot=True
            )
            logger.debug(f"Saved bot message: {bot_message.id}")

            return Response({
                'user_message': ChatbotMessageSerializer(user_message).data,
                'bot_response': ChatbotMessageSerializer(bot_message).data
            }, status=status.HTTP_201_CREATED)

        except ChatbotConversation.DoesNotExist:
            logger.error(f"Conversation {pk} not found")
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Unexpected error in send_message: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
