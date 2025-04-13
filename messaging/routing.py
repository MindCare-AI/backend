# messaging/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Existing conversation endpoint
    re_path(
        r"^ws/messaging/(?P<conversation_id>\d+)/$",
        consumers.ConversationConsumer.as_asgi(),
    ),
    
    # User presence endpoint
    re_path(r"^ws/presence/$", consumers.PresenceConsumer.as_asgi()),
]
