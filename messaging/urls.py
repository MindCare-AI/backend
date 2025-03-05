# messaging/urls.py
from django.urls import path
from .views import (
    ConversationListCreateView,
    MessageListCreateView,
    GroupChatCreateView,
    ChatbotConversationView,
    MessageReactionView,
    MessageSearchView,
    GroupManagementView,
    ConversationDetailView,
)

urlpatterns = [
    # Existing endpoints
    path(
        "conversations/",
        ConversationListCreateView.as_view(),
        name="conversation-list-create",
    ),
    path(
        "conversations/<int:pk>/",
        ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/<int:conversation_id>/messages/",
        MessageListCreateView.as_view(),
        name="message-list-create",
    ),
    path("groups/", GroupChatCreateView.as_view(), name="group-create"),
    path("chatbot/", ChatbotConversationView.as_view(), name="chatbot-conversation"),
    # New endpoints
    path(
        "messages/<int:message_id>/reactions/",
        MessageReactionView.as_view(),
        name="message-reactions",
    ),
    path("messages/search/", MessageSearchView.as_view(), name="message-search"),
    path(
        "groups/<int:group_id>/", GroupManagementView.as_view(), name="group-management"
    ),
]
