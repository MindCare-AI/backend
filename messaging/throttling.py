from rest_framework.throttling import UserRateThrottle


class MessageRateThrottle(UserRateThrottle):
    rate = "60/minute"


class ChatbotRateThrottle(UserRateThrottle):
    rate = "30/minute"
