# core/utils.py
from django.utils.deprecation import MiddlewareMixin
import threading

_request_local = threading.local()


def get_current_request():
    """Get the current request from thread local storage."""
    return getattr(_request_local, "request", None)


def set_current_request(request):
    """Set the current request in thread local storage."""
    _request_local.request = request


class RequestMiddleware(MiddlewareMixin):
    """Middleware to store request in thread local storage."""

    def process_request(self, request):
        """Store request in thread local storage."""
        set_current_request(request)

    def process_response(self, request, response):
        """Clean up thread local storage."""
        set_current_request(None)
        return response

    def process_exception(self, request, exception):
        """Clean up thread local storage on exceptions."""
        set_current_request(None)
        return None
