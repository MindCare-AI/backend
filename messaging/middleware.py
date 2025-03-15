from cryptography.fernet import Fernet
from django.conf import settings
from rest_framework.response import Response


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
