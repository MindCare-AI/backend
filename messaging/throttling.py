# messaging/throttling.py
from rest_framework.throttling import UserRateThrottle
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class BaseMessageThrottle(UserRateThrottle):
    """Base throttle class for messaging rate limits"""

    def get_cache_key(self, request, view):
        """Get cache key with enhanced staff and premium user handling"""
        user = request.user

        # No throttling for staff or premium users
        if user.is_staff or getattr(user, "is_premium", False):
            return None

        # Get custom rate for user type if defined
        if hasattr(user, "user_type"):
            custom_rate = settings.USER_TYPE_THROTTLE_RATES.get(user.user_type)
            if custom_rate:
                self.rate = custom_rate

        return super().get_cache_key(request, view)

    def allow_request(self, request, view):
        """Enhanced allowance check with logging"""
        allowed = super().allow_request(request, view)

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for user {request.user.id} "
                f"in scope {self.scope}"
            )

        return allowed


class MessageRateThrottle(BaseMessageThrottle):
    """General message rate throttling"""

    scope = "message_default"
    rate = settings.THROTTLE_RATES.get("message_default", "60/minute")


class TypingIndicatorThrottle(BaseMessageThrottle):
    """Throttle for typing indicator updates"""

    scope = "typing"
    rate = settings.THROTTLE_RATES.get("typing", "30/minute")


class ChatbotRateThrottle(BaseMessageThrottle):
    """Chatbot-specific rate throttling"""

    scope = "chatbot"
    rate = settings.THROTTLE_RATES.get("chatbot", "30/minute")


class GroupMessageThrottle(BaseMessageThrottle):
    """Group message rate throttling"""

    scope = "group_message"
    rate = settings.THROTTLE_RATES.get("group_message", "10/min")


class OneToOneMessageThrottle(BaseMessageThrottle):
    """One-to-one message rate throttling"""

    scope = "one_to_one_message"
    rate = settings.THROTTLE_RATES.get("one_to_one_message", "200/hour")


class BurstMessageThrottle(BaseMessageThrottle):
    """Burst message prevention"""

    scope = "burst_message"
    rate = settings.THROTTLE_RATES.get("burst_message", "10/minute")
