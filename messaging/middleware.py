# messaging/middleware.py
from cryptography.fernet import Fernet
from django.conf import settings
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)

class MessageEncryptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY)

    def __call__(self, request):
        response = self.get_response(request)

        if isinstance(response, Response) and "messages" in response.data:
            response.data["messages"] = [
                self._encrypt_message(msg) for msg in response.data["messages"]
            ]
        return response

    def _encrypt_message(self, message):
        message["content"] = self.cipher.encrypt(message["content"].encode()).decode()
        return message

class RealTimeMiddleware:
    """Middleware to handle real-time updates for messaging actions"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.channel_layer = get_channel_layer()

    def __call__(self, request):
        response = self.get_response(request)
        
        try:
            # Check if this is a messaging action that needs real-time updates
            if self._should_send_update(request, response):
                self._send_websocket_update(request, response)
        except Exception as e:
            logger.error(f"Error in RealTimeMiddleware: {str(e)}", exc_info=True)
            
        return response

    def _should_send_update(self, request, response):
        """Determine if the request should trigger a real-time update"""
        is_messaging_path = 'messages' in request.path
        is_modifying_method = request.method in ['POST', 'PATCH', 'DELETE']
        is_successful = response.status_code in [200, 201]
        
        return is_messaging_path and is_modifying_method and is_successful

    def _send_websocket_update(self, request, response):
        """Send WebSocket update for real-time messaging"""
        try:
            # Extract conversation ID from path
            conversation_id = self._extract_conversation_id(request.path)
            if not conversation_id:
                return

            # Prepare update data
            update_data = {
                'type': 'message.update',
                'action': request.method.lower(),
                'conversation_id': conversation_id,
                'data': response.data
            }

            # Send to appropriate group
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                update_data
            )
            
            logger.debug(f"Sent WebSocket update for conversation {conversation_id}")
            
        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {str(e)}", exc_info=True)

    def _extract_conversation_id(self, path):
        """Extract conversation ID from request path"""
        try:
            # Example path: /api/v1/messaging/one_to_one/1/messages/
            parts = path.split('/')
            for i, part in enumerate(parts):
                if part in ['one_to_one', 'groups', 'chatbot'] and i + 1 < len(parts):
                    return parts[i + 1]
            return None
        except Exception:
            return None
