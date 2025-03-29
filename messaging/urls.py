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
    # One-to-One Message Actions
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
    path("groups/", group_conversation_list, name="group-conversation-list"),
    path(
        "groups/<int:pk>/", group_conversation_detail, name="group-conversation-detail"
    ),
    path("groups/messages/", group_message_list, name="group-message-list"),
    path(
        "groups/messages/<int:pk>/", group_message_detail, name="group-message-detail"
    ),
    # Group Participant Management (ADD THESE ENDPOINTS)
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
    # Group Message Actions
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
