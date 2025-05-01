# messaging/routing.py
from django.urls import path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    # WebSocket URL for individual conversations (works for both one-to-one and group)
    path("ws/conversation/<str:conversation_id>/", ChatConsumer.as_asgi()),
]

# Export the URL patterns for inclusion in the ASGI application
urlpatterns = websocket_urlpatterns
