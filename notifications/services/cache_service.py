# notifications/services/cache_service.py
from django.core.cache import cache


class NotificationCacheService:
    @staticmethod
    def get_cache_key(user_id: int) -> str:
        return f"user_notifications_{user_id}"

    @staticmethod
    def invalidate_cache(user_id: int) -> None:
        cache.delete(NotificationCacheService.get_cache_key(user_id))

    @staticmethod
    def get_cached_notifications(user_id: int):
        return cache.get(NotificationCacheService.get_cache_key(user_id))
