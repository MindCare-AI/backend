#messaging/tasks.py
from celery import shared_task
from .models import Conversation, Message
from django.contrib.auth import get_user_model
from messaging.chatbot.chatbot import get_ollama_response
from django.utils.timezone import now
from messaging.firebase_client import push_message  # New import
from asgiref.sync import async_to_sync
import json

User = get_user_model()


@shared_task(bind=True)
def generate_chatbot_response(self, conversation_id, user_id, message_content):
    try:
        conversation = Conversation.objects.get(pk=conversation_id)
        user = User.objects.get(pk=user_id)

        history = list(
            Message.objects.filter(conversation=conversation)
            .order_by("-timestamp")[:3]
            .values("content", "is_chatbot")
        )

        chatbot_content = get_ollama_response(
            message_content, conversation_history=history
        )

        bot_message = Message.objects.create(
            conversation=conversation,
            sender=user,  # Optionally change this to a dedicated chatbot user
            content=chatbot_content,
            is_chatbot=True,
        )

        # Push the bot message to Firebase instead of using channels
        firebase_data = {
            "message": chatbot_content,
            "sender": "Samantha",  # Chatbot name
            "timestamp": str(bot_message.timestamp),
            "message_id": bot_message.id,
        }
        push_message(conversation_id, firebase_data)

        return True
    except Exception as e:
        return False
