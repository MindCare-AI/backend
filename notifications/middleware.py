# notifications/middleware.py
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
import logging

logger = logging.getLogger(__name__)


class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        if scope["type"] == "websocket":
            scope["user"] = await self.get_user(scope)
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, scope):
        try:
            if "session" not in scope:
                logger.warning("No session found in WebSocket scope")
                return AnonymousUser()

            session_key = scope["session"].get("_auth_user_id")
            if not session_key:
                logger.warning("No user ID found in session")
                return AnonymousUser()

            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=session_key)
            logger.debug(f"Successfully authenticated WebSocket user: {user.username}")
            return user

        except Exception as e:
            logger.error(f"WebSocket authentication error: {str(e)}")
            return AnonymousUser()
