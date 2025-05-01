# messaging/throttling.py
from rest_framework.throttling import UserRateThrottle
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class UserRateThrottle(UserRateThrottle):
    """
    Throttle for API requests by authenticated users.
    Default rate: 60/minute
    """
    scope = 'user'
    rate = getattr(settings, 'API_THROTTLE_RATE_USER', '60/minute')


class MessageRateThrottle(UserRateThrottle):
    """
    Stricter throttle for message creation.
    Default rate: 30/minute
    """
    scope = 'message'
    rate = getattr(settings, 'API_THROTTLE_RATE_MESSAGE', '30/minute')


class GroupMessageThrottle(UserRateThrottle):
    """
    Throttle for group messaging with reasonable limits.
    Default rate: 20/minute
    """
    scope = 'group_message'
    rate = getattr(settings, 'API_THROTTLE_RATE_GROUP_MESSAGE', '20/minute')


class ReadReceiptThrottle(UserRateThrottle):
    """
    Throttle for read receipts to prevent flooding.
    Default rate: 50/minute
    """
    scope = 'read_receipt'
    rate = getattr(settings, 'API_THROTTLE_RATE_READ_RECEIPT', '50/minute')


class TypingIndicatorThrottle(UserRateThrottle):
    """
    Throttle for typing indicators with a higher rate because they are sent frequently.
    Default rate: 20/10seconds
    """
    scope = 'typing'
    rate = getattr(settings, 'API_THROTTLE_RATE_TYPING', '20/10second')


class ReactionThrottle(UserRateThrottle):
    """
    Throttle for message reactions.
    Default rate: 40/minute
    """
    scope = 'reaction'
    rate = getattr(settings, 'API_THROTTLE_RATE_REACTION', '40/minute')


class BurstRateThrottle(UserRateThrottle):
    """
    More permissive throttle for burst operations.
    Default rate: 120/minute
    """
    scope = 'burst'
    rate = getattr(settings, 'API_THROTTLE_RATE_BURST', '120/minute')
