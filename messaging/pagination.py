# messaging/pagination.py
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

# Simple placeholder encryption function
def encrypt(content):
    # For now, return content unchanged – replace with actual encryption
    return content

class CustomMessagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "results": data,
            }
        )


class EncryptedMessagePagination(CustomMessagePagination):
    def get_paginated_response(self, data):
        encrypted_data = [
            {**msg, 'content': encrypt(msg['content'])} for msg in data
        ]
        return super().get_paginated_response(encrypted_data)
