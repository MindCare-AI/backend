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
    ordering = '-timestamp'
    cursor_query_param = 'cursor'
    
    def get_paginated_response(self, data):
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'total_count': self.page.paginator.count
        })

class EncryptedMessagePagination(MessagePagination):
    """Cursor pagination with content encryption"""
    
    def __init__(self):
        super().__init__()
        self.cipher = Fernet(settings.MESSAGE_ENCRYPTION_KEY)

    def get_paginated_response(self, data):
        try:
            # Encrypt message content
            encrypted_data = [
                {
                    **msg,
                    'content': self._encrypt_content(msg.get('content', ''))
                }
                for msg in data
            ]
            
            return super().get_paginated_response(encrypted_data)
            
        except Exception as e:
            logger.error(f"Error encrypting paginated data: {str(e)}", exc_info=True)
            return Response({'error': 'Failed to process messages'}, status=500)

    def _encrypt_content(self, content):
        """Encrypt message content"""
        if not content:
            return ''
        try:
            return self.cipher.encrypt(content.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            return ''

class CustomMessagePagination(CursorPagination):
    """Custom cursor pagination for messages"""
    page_size = 50
    ordering = '-timestamp'
    cursor_query_param = 'cursor'
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'results': data
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'next': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'previous': {
                    'type': 'string',
                    'format': 'uri',
                    'nullable': True
                },
                'count': {
                    'type': 'integer'
                },
                'results': schema
            }
        }
