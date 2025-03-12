# messaging/tasks.py
from celery import shared_task
from .models.chatbot import ChatbotMessage, ChatbotConversation
from .services.chatbot import get_chatbot_response
from .services.firebase import push_message
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_chatbot_response(self, conversation_id: int, message_content: str):
    try:
        conversation = ChatbotConversation.objects.get(id=conversation_id)

        # Get bot response
        response = get_chatbot_response(message_content, [])

        # Create message in database
        message = ChatbotMessage.objects.create(
            conversation=conversation, content=response, is_bot=True
        )

        return True
    except Exception as e:
        logger.error(f"Error processing chatbot response: {e}")
        self.retry(countdown=2 ** self.request.retries)
