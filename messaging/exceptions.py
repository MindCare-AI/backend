# messaging/exceptions.py


class WebSocketAuthenticationError(Exception):
    """Exception raised when WebSocket authentication fails."""

    pass


class WebSocketConnectionError(Exception):
    """Exception raised when a WebSocket connection cannot be established."""

    pass


class WebSocketMessageError(Exception):
    """Exception raised when there's an error sending or processing WebSocket messages."""

    pass


class ConversationAccessError(Exception):
    """Exception raised when a user tries to access a conversation they aren't part of."""

    pass


class MessageDeliveryError(Exception):
    """Exception raised when a message cannot be delivered."""

    pass


class RateLimitExceededError(Exception):
    """Exception raised when a user exceeds rate limits for message sending."""

    pass
