# notifications/decorators.py
from django.core.cache import cache
from functools import wraps


class RateLimitExceeded(Exception):
    pass


def rate_limit_notifications(timeout=60):
    def decorator(func):
        @wraps(func)
        def wrapper(user_id, *args, **kwargs):
            cache_key = f"notification_rate_limit_{user_id}"
            if cache.get(cache_key):
                raise RateLimitExceeded(f"Rate limit exceeded for user {user_id}")
            cache.set(cache_key, True, timeout)
            return func(user_id, *args, **kwargs)

        return wrapper

    return decorator
