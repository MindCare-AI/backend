# messaging/urls.py
from django.urls import path
from .views.one_to_one import OneToOneConversationViewSet, OneToOneMessageViewSet
from .views.group import GroupConversationViewSet, GroupMessageViewSet
from .views.chatbot import ChatbotConversationViewSet

urlpatterns = [
    # One-to-One Messaging
    path(
        "one_to_one/",
        OneToOneConversationViewSet.as_view({"get": "list", "post": "create"}),
        name="one-to-one-conversation-list",
    ),
    path(
        "one_to_one/<int:pk>/",
        OneToOneConversationViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="one-to-one-conversation-detail",
    ),
    path(
        "one_to_one/messages/",
        OneToOneMessageViewSet.as_view(
            {
                "get": "list",
                "post": "create",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="one-to-one-message-list",
    ),
    path(
        "one_to_one/messages/<int:pk>/",
        OneToOneMessageViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="one-to-one-message-detail",
    ),
    path(
        "one_to_one/messages/<int:pk>/reactions/",
        OneToOneMessageViewSet.as_view(
            {"post": "add_reaction", "delete": "remove_reaction"}
        ),
        name="one-to-one-message-reactions",
    ),
    path(
        "one_to_one/messages/<int:pk>/edit_history/",
        OneToOneMessageViewSet.as_view({"get": "edit_history"}),
        name="one-to-one-message-edit-history",
    ),
    path(
        "one_to_one/<int:pk>/typing/",
        OneToOneConversationViewSet.as_view({"post": "typing"}),
        name="one-to-one-typing",
    ),
    path(
        "one_to_one/<int:pk>/search/",
        OneToOneConversationViewSet.as_view({"get": "search"}),
        name="one-to-one-search",
    ),
    # Group Messaging
    path(
        "groups/",
        GroupConversationViewSet.as_view({"get": "list", "post": "create"}),
        name="group-conversation-list",
    ),
    path(
        "groups/<int:pk>/",
        GroupConversationViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="group-conversation-detail",
    ),
    path(
        "groups/messages/",
        GroupMessageViewSet.as_view({"get": "list", "post": "create"}),
        name="group-message-list",
    ),
    path(
        "groups/messages/<int:pk>/",
        GroupMessageViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="group-message-detail",
    ),
    path(
        "groups/<int:pk>/add_participant/",
        GroupConversationViewSet.as_view({"post": "add_participant"}),
        name="group-add-participant",
    ),
    path(
        "groups/<int:pk>/remove_participant/",
        GroupConversationViewSet.as_view({"post": "remove_participant"}),
        name="group-remove-participant",
    ),
    path(
        "groups/<int:pk>/add_moderator/",
        GroupConversationViewSet.as_view({"post": "add_moderator"}),
        name="group-add-moderator",
    ),
    path(
        "groups/<int:pk>/moderators/",
        GroupConversationViewSet.as_view({"get": "moderators"}),
        name="group-moderators",
    ),
    path(
        "groups/<int:pk>/pin_message/",
        GroupConversationViewSet.as_view({"post": "pin_message"}),
        name="group-pin-message",
    ),
    path(
        "groups/messages/<int:pk>/reactions/",
        GroupMessageViewSet.as_view(
            {"post": "add_reaction", "delete": "remove_reaction"}
        ),
        name="group-message-reactions",
    ),
    path(
        "groups/messages/<int:pk>/edit_history/",
        GroupMessageViewSet.as_view({"get": "edit_history"}),
        name="group-message-edit-history",
    ),
    path(
        "groups/anonymous/",
        GroupConversationViewSet.as_view({"post": "create_anonymous"}),
        name="create-anonymous-group",
    ),
    path(
        "groups/search_messages/",
        GroupConversationViewSet.as_view({"get": "search_messages"}),
        name="group-search-messages",
    ),
    # Chatbot
    path(
        "chatbot/",
        ChatbotConversationViewSet.as_view({"get": "list", "post": "create"}),
        name="chatbot-conversation-list",
    ),
    path(
        "chatbot/<int:pk>/",
        ChatbotConversationViewSet.as_view({"get": "retrieve"}),
        name="chatbot-conversation-detail",
    ),
    path(
        "chatbot/<int:pk>/send_message/",
        ChatbotConversationViewSet.as_view({"post": "send_message"}),
        name="chatbot-send-message",
    ),
    # Unified Search
    path(
        "search/",
        GroupConversationViewSet.as_view({"get": "search_all"}),
        name="search-all-conversations",
    ),
]
