import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from core.middleware import UnifiedWebSocketAuthMiddleware
from messaging.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mindcare.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": UnifiedWebSocketAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        ),
    }
)
