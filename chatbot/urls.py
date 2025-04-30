from django.urls import path
from .views import ChatbotConversationViewSet

urlpatterns = [
    path("",ChatbotConversationViewSet.as_view({"get": "list", "post": "create"}),name="chatbot-conversation-list",),
   
    path(
        "<int:pk>/",
        ChatbotConversationViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy"
        }),
        name="chatbot-conversation-detail",
    ),
    path(
        "<int:pk>/send_message/",
        ChatbotConversationViewSet.as_view({"post": "send_message"}),
        name="chatbot-send-message",
    ),
]