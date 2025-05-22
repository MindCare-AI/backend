# messaging/urls.py
from django.urls import path
from .views.one_to_one import OneToOneConversationViewSet, OneToOneMessageViewSet
from .views.group import GroupConversationViewSet, GroupMessageViewSet
from .views.offline import OfflineMessageSyncView
from messaging.views.all_conversations import AllConversationsView

urlpatterns = [
    # ==============================
    # One-to-One Conversation Endpoints
    # ==============================
    path(
        "one_to_one/",
        OneToOneConversationViewSet.as_view({"get": "list", "post": "create"}),
        name="one_to_one_conversation_list",
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
        name="one_to_one_conversation_detail",
    ),
    path(
        "one_to_one/<int:pk>/messages/",
        OneToOneConversationViewSet.as_view({"get": "messages"}),
        name="one_to_one_messages",
    ),
    path(
        "one_to_one/<int:pk>/typing/",
        OneToOneConversationViewSet.as_view({"post": "typing"}),
        name="one_to_one_typing",
    ),
    path(
        "one_to_one/<int:pk>/search/",
        OneToOneConversationViewSet.as_view({"get": "search"}),
        name="one_to_one_search",
    ),
    # ==============================
    # One-to-One Message Endpoints
    # ==============================
    path(
        "one_to_one/messages/",
        OneToOneMessageViewSet.as_view({"get": "list", "post": "create"}),
        name="one_to_one_message_list",
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
        name="one_to_one_message_detail",
    ),
    # ==============================
    # Group Conversation Endpoints
    # ==============================
    path(
        "groups/",
        GroupConversationViewSet.as_view({"get": "list", "post": "create"}),
        name="group_conversation_list",
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
        name="group_conversation_detail",
    ),
    path(
        "groups/<int:pk>/add_moderator/",
        GroupConversationViewSet.as_view({"post": "add_moderator"}),
        name="group_add_moderator",
    ),
    path(
        "groups/<int:pk>/moderators/",
        GroupConversationViewSet.as_view({"get": "moderators"}),
        name="group_moderators",
    ),
    path(
        "groups/<int:pk>/add_participant/",
        GroupConversationViewSet.as_view({"post": "add_participant"}),
        name="group_add_participant",
    ),
    path(
        "groups/<int:pk>/remove_participant/",
        GroupConversationViewSet.as_view({"post": "remove_participant"}),
        name="group_remove_participant",
    ),
    path(
        "groups/<int:pk>/pin_message/",
        GroupConversationViewSet.as_view({"post": "pin_message"}),
        name="group_pin_message",
    ),
    path(
        "groups/search_messages/",
        GroupConversationViewSet.as_view({"get": "search_messages"}),
        name="group_search_messages",
    ),
    path(
        "groups/search_groups/",
        GroupConversationViewSet.as_view({"get": "search_groups"}),
        name="group_search_groups",
    ),
    path(
        "groups/search_all/",
        GroupConversationViewSet.as_view({"get": "search_all"}),
        name="group_search_all",
    ),
    # ==============================
    # Group Message Endpoints
    # ==============================
    path(
        "groups/messages/",
        GroupMessageViewSet.as_view({"get": "list", "post": "create"}),
        name="group_message_list",
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
        name="group_message_detail",
    ),
    # ==============================
    # Offline Messaging Sync Endpoint
    # ==============================
    path(
        "offline/messages/", OfflineMessageSyncView.as_view(), name="offline_messages"
    ),
    # ==============================
    # All Conversations Endpoint
    # ==============================
    path(
        "all/", AllConversationsView.as_view(), name="all_conversations"
    ),
]
