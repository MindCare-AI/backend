from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from .models import Conversation, Message
from django.contrib.auth import get_user_model
from messaging.chatbot.chatbot import get_ollama_response
from django.utils.timezone import now


@shared_task(bind=True, max_retries=3)
def generate_chatbot_response(self, conversation_id, user_id, message_content):
    try:
        conversation = Conversation.objects.get(pk=conversation_id)
        user = get_user_model().objects.get(pk=user_id)

        # Get conversation history
        history = (
            Message.objects.filter(conversation=conversation, timestamp__lt=now())
            .order_by("-timestamp")[:3]
            .values("content", "is_chatbot")
        )

        # Get chatbot response with context
        chatbot_content = get_ollama_response(
            message_content, conversation_history=list(history)
        )

        # Create message
        Message.objects.create(
            conversation=conversation,
            sender=user,
            content=chatbot_content,
            is_chatbot=True,
        )
        return True
    except Exception as e:
        try:
            self.retry(countdown=2**self.request.retries)
        except MaxRetriesExceededError:
            print(f"Failed after 3 retries: {str(e)}")
        return False
