# messaging/routing.py
from django.urls import path
from .consumers import OneToOneChatConsumer, GroupChatConsumer

websocket_urlpatterns = [
    # WebSocket URL for one-to-one conversations
    path("ws/one-to-one/<str:conversation_id>/", OneToOneChatConsumer.as_asgi()),
    # WebSocket URL for group conversations
    path("ws/group/<str:conversation_id>/", GroupChatConsumer.as_asgi()),
]

# Export the URL patterns for inclusion in the ASGI application
urlpatterns = websocket_urlpatterns
