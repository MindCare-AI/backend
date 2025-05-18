# chatbot/urls.py
from django.urls import path
from .views import ChatbotViewSet

chatbot_list = ChatbotViewSet.as_view(
    {
        "get": "list",
        "post": "create",
    }
)

chatbot_detail = ChatbotViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

chatbot_send_message = ChatbotViewSet.as_view(
    {
        "post": "send_message",
    }
)

urlpatterns = [
    path("", chatbot_list, name="chatbot-conversation-list"),
    path("", chatbot_detail, name="chatbot-conversation-detail"),
    path(
        "<int:pk>/send_message/",
        chatbot_send_message,
        name="chatbot-send-message",
    ),
]

# Example request body for the send_message endpoint
# POST request to /api/v1/chatbot/9/send_message/
# JSON body (simple format):
# {
#   "content": "Hello, can you help me with my anxiety?"
# }
#
# OR JSON body (structured format):
# {
#   "user_message": {
#     "content": "Hello, can you help me with my anxiety?"
#   }
# }
