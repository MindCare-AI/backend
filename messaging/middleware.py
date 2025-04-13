# messaging/middleware.py
from cryptography.fernet import Fernet
from django.conf import settings
from rest_framework.response import Response
from channels.layers import get_channel_layer
import logging
from django.utils import timezone
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import (
    TokenError,
    InvalidToken,
)  # Add this import
from urllib.parse import parse_qs

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
        # Define conversation URL patterns for more robust path matching
        self.conversation_patterns = {
            "one_to_one": r"/api/messaging/one_to_one/(\d+)",
            "groups": r"/api/messaging/groups/(\d+)",
            "chatbot": r"/api/messaging/chatbot/(\d+)",
        }

    def __call__(self, request):
        response = self.get_response(request)

        try:
            # Skip if channel layer is not available
            if not self.channel_layer:
                return response

            # Check if this is a messaging action that needs real-time updates
            if self._should_send_update(request, response):
                self._send_websocket_update(request, response)
        except Exception as e:
            logger.error(f"Error in RealTimeMiddleware: {str(e)}", exc_info=True)

        return response

    def _should_send_update(self, request, response):
        """Determine if the request should trigger a real-time update"""
        # Only for messaging endpoints, certain methods, and successful responses
        is_messaging_path = request.path.startswith("/api/messaging/")
        is_modifying_method = request.method in ["POST", "PUT", "PATCH", "DELETE"]
        is_successful = 200 <= response.status_code < 300

        return is_messaging_path and is_modifying_method and is_successful

    def _extract_conversation_id(self, path):
        """Extract conversation ID from request path more reliably using regex"""
        import re

        try:
            # Try to match path against known conversation patterns
            for conv_type, pattern in self.conversation_patterns.items():
                match = re.search(pattern, path)
                if match:
                    conversation_id = match.group(1)
                    logger.debug(
                        f"Extracted conversation ID {conversation_id} from path {path} (type: {conv_type})"
                    )
                    return conversation_id

            # If no direct match, try to find any numeric ID that might be a conversation ID
            segments = path.strip("/").split("/")
            for i, segment in enumerate(segments):
                if segment in [
                    "conversation",
                    "conversations",
                    "messages",
                ] and i + 1 < len(segments):
                    potential_id = segments[i + 1]
                    if potential_id.isdigit():
                        logger.debug(
                            f"Found potential conversation ID {potential_id} from path {path}"
                        )
                        return potential_id

            logger.debug(f"Could not extract conversation ID from path: {path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting conversation ID: {str(e)}", exc_info=True)
            return None

    def _send_websocket_update(self, request, response):
        """Send WebSocket update for real-time messaging"""
        try:
            conversation_id = self._extract_conversation_id(request.path)
            if not conversation_id:
                return

            # Import the message delivery service
            from messaging.services.message_delivery import message_delivery_service

            # Determine action type based on method and endpoint
            if "message" in request.path.lower():
                if request.method == "POST":
                    action = "message_created"
                elif request.method in ["PUT", "PATCH"]:
                    action = "message_updated"
                elif request.method == "DELETE":
                    action = "message_deleted"
                else:
                    action = "message_action"
            else:
                action = "conversation_updated"

            # Prepare message data
            message_data = {
                "user_id": str(request.user.id),
                "username": request.user.username,
                "data": response.data if hasattr(response, "data") else {},
                "timestamp": timezone.now().isoformat(),
                "conversation_id": conversation_id,
            }

            # Use the unified service to send the update
            message_delivery_service.send_message_update(
                conversation_id=conversation_id,
                event_type=action,
                message_data=message_data,
                user_id=str(request.user.id),
            )

            logger.debug(
                f"Sent WebSocket update for {action} in conversation {conversation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {str(e)}", exc_info=True)


class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        try:
            query_string = scope.get("query_string", b"").decode()
            query_params = parse_qs(query_string)
            token = query_params.get("token", [None])[0]

            if not token:
                logger.warning("No token provided in WebSocket connection")
                scope["user"] = AnonymousUser()
                return await super().__call__(scope, receive, send)

            user = await self.get_user_from_token(token)
            if not user:
                logger.warning("Invalid token or user not found")
                scope["user"] = AnonymousUser()
                return await super().__call__(scope, receive, send)

            scope["user"] = user
            return await super().__call__(scope, receive, send)

        except Exception as e:
            logger.error(f"WebSocket auth error: {str(e)}", exc_info=True)
            scope["user"] = AnonymousUser()
            return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            User = get_user_model()
            return User.objects.get(id=user_id)
        except (TokenError, InvalidToken, User.DoesNotExist) as e:
            logger.warning(f"Token validation failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error in token validation: {str(e)}", exc_info=True
            )
            return None


class OnlineStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Update last activity time
            request.user.last_activity = timezone.now()
            request.user.save(update_fields=["last_activity"])
        return self.get_response(request)
