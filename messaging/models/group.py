# messaging/models/group.py
from django.db import models
from django.conf import settings
from .base import BaseConversation, BaseMessage


class GroupConversation(BaseConversation):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    moderators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="moderated_groups"
    )
    is_private = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class GroupMessage(BaseMessage):
    conversation = models.ForeignKey(
        GroupConversation, on_delete=models.CASCADE, related_name="messages"
    )
    message_type = models.CharField(
        max_length=10, choices=[("text", "Text"), ("system", "System")], default="text"
    )
    media = models.FileField(
        upload_to="uploads/group/",
        blank=True,
        null=True,
        help_text="Upload media files (images, videos, PDFs, etc.)",
    )

    def clean(self):
        super().clean()
        if self.media:
            from media_handler.utils import validate_file_extension

            validate_file_extension(self.media.name, [".jpg", ".png", ".mp4", ".pdf"])

    def __str__(self):
        return f"Message by {self.sender} in {self.conversation}"
