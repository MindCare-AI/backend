# messaging/tasks.py
from celery import shared_task
from .models.chatbot import ChatbotMessage
from .services.chatbot import chatbot_service
import logging

logger = logging.getLogger(__name__)


def exponential_backoff(retries):
    """Calculate exponential backoff delay in seconds"""
    return 2**retries * 60  # 1min, 2min, 4min, etc.


@shared_task(
    bind=True, autoretry_for=(Exception,), max_retries=3, countdown=exponential_backoff
)
def process_chatbot_response(self, conversation_id, message_id):
    """
    Process chatbot response asynchronously with error handling and retries.
    Uses exponential backoff for retries.
    """
    try:
        # Get the user's message and conversation
        user_message = ChatbotMessage.objects.get(id=message_id)
        conversation = user_message.conversation

        # Get conversation history (last 10 messages) in chronological order
        history = list(
            conversation.messages.filter(timestamp__lt=user_message.timestamp).order_by(
                "-timestamp"
            )[:10]
        )
        history.reverse()  # Put in chronological order

        # Format history for chatbot service
        formatted_history = [
            {
                "content": msg.content,
                "is_bot": msg.is_bot,
                "sender": "Samantha" if msg.is_bot else user_message.sender.username,
            }
            for msg in history
        ]

        # Get chatbot response
        response = chatbot_service.get_response(
            message=user_message.content, history=formatted_history
        )

        if not response["success"]:
            logger.error(f"Chatbot service error: {response.get('error')}")
            error_message = response["response"]  # Use provided fallback message
        else:
            error_message = None

        # Create bot response message
        ChatbotMessage.objects.create(
            conversation=conversation,
            content=error_message or response["response"],
            is_bot=True,
            metadata={
                "error": bool(error_message),
                "attempt": self.request.retries + 1,
            },
        )

    except ChatbotMessage.DoesNotExist:
        logger.error(f"Message {message_id} not found")
        raise
    except Exception as e:
        logger.error(f"Chatbot processing failed: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(exc=e)

# Removed redundant exponential_backoff function definition
