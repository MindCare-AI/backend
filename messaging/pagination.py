# messaging/pagination.py
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from cryptography.fernet import Fernet
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MessagePagination(CursorPagination):
    """Base cursor pagination for messages"""

    page_size = 20
    ordering = "-timestamp"
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        return Response(
            {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
                "total_count": self.page.paginator.count,
            }
        )


class EncryptedMessagePagination(MessagePagination):
    """Cursor pagination with content encryption"""

    def __init__(self):
        super().__init__()
        self.cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY)

    def get_paginated_response(self, data):
        try:
            # Encrypt message content
            encrypted_data = [
                {**msg, "content": self._encrypt_content(msg.get("content", ""))}
                for msg in data
            ]

            return super().get_paginated_response(encrypted_data)

        except Exception as e:
            logger.error(f"Error encrypting paginated data: {str(e)}", exc_info=True)
            return Response({"error": "Failed to process messages"}, status=500)

    def _encrypt_content(self, content):
        """Encrypt message content"""
        if not content:
            return ""
        try:
            return self.cipher.encrypt(content.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            return ""


class CustomMessagePagination(CursorPagination):
    """Custom cursor pagination for messages"""

    page_size = 50
    ordering = "-timestamp"
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        count = 0
        # Handle case where self.page is a list without paginator
        if hasattr(self, 'page'):
            if hasattr(self.page, 'paginator'):
                count = self.page.paginator.count
            elif isinstance(self.page, list):
                count = len(self.page)
                
        return Response(
            {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "count": count,
                "results": data,
                "next_cursor": self.get_next_cursor(),
            }
        )

    def get_next_cursor(self):
        try:
            if hasattr(self, 'page') and self.page and hasattr(self.page, 'has_next') and self.page.has_next:
                last_item = self.page[-1]
                return str(last_item.id)
            elif isinstance(getattr(self, 'page', None), list) and len(self.page) >= self.page_size:
                # If we have exactly page_size items, there might be more
                last_item = self.page[-1]
                return str(last_item.id)
            return None
        except Exception as e:
            logger.error(f"Error getting next cursor: {str(e)}")
            return None

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "next": {"type": "string", "format": "uri", "nullable": True},
                "previous": {"type": "string", "format": "uri", "nullable": True},
                "count": {"type": "integer"},
                "results": schema,
                "next_cursor": {"type": "string", "nullable": True},
            },
        }
