from ..models.one_to_one import OneToOneMessage, OneToOneConversation
from ..models.group import GroupMessage, GroupConversation


class MessagingService:
    """Core messaging service for handling message operations"""

    def __init__(self):
        self.one_to_one_model = OneToOneMessage
        self.group_model = GroupMessage

    def send_message(self, sender, conversation_id, content, message_type="one_to_one"):
        """Send a message in a conversation"""
        if message_type == "one_to_one":
            conversation = OneToOneConversation.objects.get(id=conversation_id)
            return self.one_to_one_model.objects.create(
                sender=sender, conversation=conversation, content=content
            )
        elif message_type == "group":
            conversation = GroupConversation.objects.get(id=conversation_id)
            return self.group_model.objects.create(
                sender=sender, conversation=conversation, content=content
            )

    def get_conversation_messages(self, conversation_id, message_type="one_to_one"):
        """Get all messages in a conversation"""
        if message_type == "one_to_one":
            return self.one_to_one_model.objects.filter(
                conversation_id=conversation_id
            ).order_by("timestamp")
        elif message_type == "group":
            return self.group_model.objects.filter(
                conversation_id=conversation_id
            ).order_by("timestamp")
