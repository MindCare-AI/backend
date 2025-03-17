# notifications/middleware.py
from django.contrib.auth.middleware import RemoteUserMiddleware


class NotificationSecurityMiddleware(RemoteUserMiddleware):
    def process_request(self, request):
        # Custom middleware logic before request processing, if needed.
        super().process_request(request)

    def __call__(self, request):
        response = super().__call__(request)
        # Add security headers for notification endpoints
        if request.path.startswith("/notifications/"):
            response["Content-Security-Policy"] = "default-src 'self'"
            response["X-Content-Type-Options"] = "nosniff"
            response["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
