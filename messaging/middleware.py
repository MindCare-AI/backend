# messaging/middleware.py
from cryptography.fernet import Fernet
from django.conf import settings
from rest_framework.response import Response
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from django.core.cache import cache
from datetime import datetime
import json

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
            conversation_id = self._extract_conversation_id(request.path)
            if not conversation_id:
                logger.warning(f"Could not extract conversation ID from path: {request.path}")
                return

            # Rate limiting check
            cache_key = f"ws_update_{conversation_id}_{request.user.id}"
            if not self._check_rate_limit(cache_key):
                logger.warning(f"Rate limit exceeded for conversation {conversation_id}")
                return

            # Determine action type
            action_type = self._get_action_type(request.method)
            
            # Prepare update data with additional context
            update_data = {
                'type': 'message.update',
                'action': action_type,
                'conversation_id': conversation_id,
                'data': self._sanitize_response_data(response.data),
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'user_id': str(request.user.id),
                    'username': str(request.user),
                }
            }

            # Validate update data
            if not self._validate_update_data(update_data):
                logger.error("Invalid update data structure")
                return

            # Send to appropriate group
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                update_data
            )
            
            logger.debug(f"Successfully sent WebSocket update for conversation {conversation_id}")
            
        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {str(e)}", exc_info=True)
            
    def _get_action_type(self, method):
        """Map HTTP methods to WebSocket action types"""
        action_map = {
            'POST': 'message_created',
            'PATCH': 'message_updated',
            'DELETE': 'message_deleted',
        }
        return action_map.get(method, 'message_unknown')

    def _check_rate_limit(self, cache_key, limit=10, window=60):
        """Implement rate limiting for WebSocket updates"""
        try:
            current = cache.get(cache_key, 0)
            if current >= limit:
                return False
            cache.incr(cache_key, 1)
            cache.expire(cache_key, window)
            return True
        except Exception as e:
            logger.error(f"Rate limiting error: {str(e)}")
            return True  # Allow on error

    def _validate_update_data(self, data):
        """Validate the structure of update data"""
        required_fields = ['type', 'action', 'conversation_id', 'data']
        return all(field in data for field in required_fields)

    def _sanitize_response_data(self, data):
        """Sanitize response data for WebSocket transmission"""
        try:
            # Test JSON serialization
            json.dumps(data)
            return data
        except (TypeError, ValueError):
            # If serialization fails, return basic data structure
            return {
                'error': 'Data sanitization required',
                'timestamp': datetime.now().isoformat()
            }

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
