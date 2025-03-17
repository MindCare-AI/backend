# messaging/urls.py
from django.urls import path
from .views.one_to_one import OneToOneConversationViewSet, OneToOneMessageViewSet
from .views.group import GroupConversationViewSet, GroupMessageViewSet
from .views.chatbot import ChatbotConversationViewSet

# One-to-One Messaging
one_to_one_conversation_list = OneToOneConversationViewSet.as_view(
    {"get": "list", "post": "create"}
)
one_to_one_conversation_detail = OneToOneConversationViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
one_to_one_message_list = OneToOneMessageViewSet.as_view(
    {"get": "list", "post": "create"}
)
one_to_one_message_detail = OneToOneMessageViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

# Group Messaging
group_conversation_list = GroupConversationViewSet.as_view(
    {"get": "list", "post": "create"}
)
group_conversation_detail = GroupConversationViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
group_message_list = GroupMessageViewSet.as_view({"get": "list", "post": "create"})
group_message_detail = GroupMessageViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

# Chatbot
chatbot_conversation_create = ChatbotConversationViewSet.as_view({"post": "create"})
chatbot_conversation_detail = ChatbotConversationViewSet.as_view({"get": "retrieve"})
chatbot_send_message = ChatbotConversationViewSet.as_view({"post": "send_message"})

urlpatterns = [
    # One-to-One Messaging
    path(
        "one_to_one/", one_to_one_conversation_list, name="one-to-one-conversation-list"
    ),
    path(
        "one_to_one/<int:pk>/",
        one_to_one_conversation_detail,
        name="one-to-one-conversation-detail",
    ),
    path(
        "one_to_one/messages/", one_to_one_message_list, name="one-to-one-message-list"
    ),
    path(
        "one_to_one/messages/<int:pk>/",
        one_to_one_message_detail,
        name="one-to-one-message-detail",
    ),
    # New endpoints for One-to-One Messaging
    path(
        "one_to_one/<int:pk>/typing/",
        OneToOneConversationViewSet.as_view({"post": "typing"}),
        name="typing",
    ),
    path(
        "one_to_one/<int:pk>/search/",
        OneToOneConversationViewSet.as_view({"get": "search"}),
        name="search",
    ),
    # Group Messaging
    path("groups/", group_conversation_list, name="group-conversation-list"),
    path(
        "groups/<int:pk>/", group_conversation_detail, name="group-conversation-detail"
    ),
    path("groups/messages/", group_message_list, name="group-message-list"),
    path(
        "groups/messages/<int:pk>/", group_message_detail, name="group-message-detail"
    ),
    path(
        "groups/anonymous/",
        GroupConversationViewSet.as_view({"post": "create_anonymous"}),
        name="create-anonymous-group",
    ),
    # Chatbot
    path("chatbot/", chatbot_conversation_create, name="chatbot-conversation-create"),
    path(
        "chatbot/<int:pk>/",
        chatbot_conversation_detail,
        name="chatbot-conversation-detail",
    ),
    path(
        "chatbot/<int:pk>/send_message/",
        chatbot_send_message,
        name="chatbot-send-message",
    ),
]
