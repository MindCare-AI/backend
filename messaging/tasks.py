# messaging/tasks.py
from celery import shared_task
from .models.chatbot import ChatbotMessage, ChatbotConversation
from .services.chatbot import get_chatbot_response as chatbot_service
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
def process_chatbot_response(self, conversation_id, message_id):
    try:
        message = ChatbotMessage.objects.get(id=message_id)
        # Retrieve up to ten messages from the conversation as history context.
        history = list(
            message.conversation.messages.values('content', 'is_bot')[:10]
        )
        
        response = chatbot_service(
            message.content,
            [{'content': msg['content'], 'is_bot': msg['is_bot']} for msg in history]
        )
        
        ChatbotMessage.objects.create(
            conversation=message.conversation,
            content=response['response'],
            is_bot=True
        )
    except Exception as e:
        logger.error(f"Chatbot processing failed: {str(e)}")
        raise self.retry(exc=e)
