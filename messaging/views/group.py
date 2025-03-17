# messaging/views/group.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Count
from django.contrib.auth import get_user_model
from django.conf import settings
import logging

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models.group import GroupConversation, GroupMessage
from ..serializers.group import GroupConversationSerializer, GroupMessageSerializer
from ..pagination import CustomMessagePagination
from notifications.services import NotificationService
from notifications.services.unified_service import UnifiedNotificationService
from celery import shared_task
from messaging.permissions import IsParticipantOrModerator
from messaging.throttling import GroupMessageThrottle  # Use the correct module name

logger = logging.getLogger(__name__)

notification_service = NotificationService()


@shared_task
def create_group_notifications(group_id, message, exclude_users=None):
    from users.models.preferences import UserPreferences  # added import

    group = GroupConversation.objects.get(id=group_id)
    for user in group.participants.exclude(id__in=exclude_users or []):
        # Check if user allows in-app notifications
        preferences = UserPreferences.objects.get_or_create(user=user)[0]
        if preferences.in_app_notifications:
            notification_service.create_group_notification(
                user=user,
                message=message,
                # ...other parameters...
            )


@extend_schema_view(
    list=extend_schema(
        description="List all group conversations where the authenticated user is a participant.",
        summary="List Group Conversations",
        tags=["Group Conversation"],
    ),
    retrieve=extend_schema(
        description="Retrieve details of a specific group conversation.",
        summary="Retrieve Group Conversation",
        tags=["Group Conversation"],
    ),
    create=extend_schema(
        description="Create a new group conversation and automatically add the creator as a participant and moderator.",
        summary="Create Group Conversation",
        tags=["Group Conversation"],
    ),
    update=extend_schema(
        description="Update details of a group conversation.",
        summary="Update Group Conversation",
        tags=["Group Conversation"],
    ),
    partial_update=extend_schema(
        description="Partially update a group conversation.",
        summary="Patch Group Conversation",
        tags=["Group Conversation"],
    ),
    destroy=extend_schema(
        description="Delete a group conversation.",
        summary="Delete Group Conversation",
        tags=["Group Conversation"],
    ),
)
class GroupConversationViewSet(viewsets.ModelViewSet):
    queryset = GroupConversation.objects.all()
    serializer_class = GroupConversationSerializer
    permission_classes = [IsParticipantOrModerator]
    throttle_classes = [GroupMessageThrottle]

    def get_queryset(self):
        """Filter conversations and optimize queries"""
        return (
            self.queryset.filter(participants=self.request.user)
            .prefetch_related("participants", "moderators")
            .annotate(
                participant_count=Count("participants"), message_count=Count("messages")
            )
        )

    @transaction.atomic
    def perform_create(self, serializer):
        """Create group with atomic transaction using unified notifications"""
        try:
            max_groups = getattr(settings, "MAX_GROUPS_PER_USER", 10)
            user_groups = GroupConversation.objects.filter(
                participants=self.request.user
            ).count()
            if user_groups >= max_groups:
                raise ValidationError(f"Maximum group limit ({max_groups}) reached")

            instance = serializer.save()
            instance.participants.add(self.request.user)
            instance.moderators.add(self.request.user)

            # Send unified notifications to all participants except the creator.
            for user in instance.participants.exclude(id=self.request.user.id):
                UnifiedNotificationService.send_notification(
                    user=user,
                    notification_type="group_update",
                    title="New Group Created",
                    message=f"Group '{instance.name}' has been created successfully.",
                    send_email=False,
                    send_in_app=True,
                    email_template="notifications/group_created.email",
                    link=f"/groups/{instance.id}/",
                    priority="high",
                    category="group",
                )

            logger.info(
                f"Group conversation {instance.id} created by user {self.request.user.id}"
            )
            return instance

        except Exception as e:
            logger.error(f"Group creation failed: {str(e)}")
            raise ValidationError(f"Failed to create group: {str(e)}")

    @extend_schema(
        description="Add a user as a moderator to the group using unified notifications.",
        summary="Add Moderator",
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"])
    def add_moderator(self, request, pk=None):
        group = self.get_object()
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "You don't have permission to add moderators."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user = get_object_or_404(get_user_model(), id=request.data.get("user_id"))
        if not group.participants.filter(id=user.id).exists():
            return Response(
                {
                    "detail": "User must be a participant before being promoted to moderator."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        group.moderators.add(user)

        # Send unified notification to the promoted user for personal update.
        UnifiedNotificationService.send_notification(
            user=user,
            notification_type="group_update",
            title="Promotion to Moderator",
            message=f"You are now a moderator in group '{group.name}'.",
            send_email=False,
            send_in_app=True,
            email_template="notifications/moderator_promotion.email",
            link=f"/groups/{group.id}/",
            priority="medium",
            category="group",
        )

        # Notify other group members (excluding the promoted user)
        for participant in group.participants.exclude(id=user.id):
            UnifiedNotificationService.send_notification(
                user=participant,
                notification_type="group_update",
                title="Group Update",
                message=f"{user.username} was promoted to moderator in group '{group.name}'.",
                send_email=False,
                send_in_app=True,
                email_template="notifications/group_update.email",
                link=f"/groups/{group.id}/",
                priority="medium",
                category="group",
            )

        return Response(
            {"detail": f"User {user.username} is now a moderator."},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        description="List all moderators of the group.",
        summary="List Moderators",
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["get"])
    def moderators(self, request, pk=None):
        group = self.get_object()
        moderator_data = [
            {
                "id": mod.id,
                "username": mod.username,
                "first_name": mod.first_name,
                "last_name": mod.last_name,
                "email": mod.email,
            }
            for mod in group.moderators.all()
        ]
        return Response(moderator_data)

    @action(detail=True, methods=["post"])
    def add_participant(self, request, pk=None):
        """Add participant to group with validation"""
        try:
            group = self.get_object()

            # Validate moderator permission
            if not group.moderators.filter(id=request.user.id).exists():
                return Response(
                    {"error": "Only moderators can add participants"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get user to add
            user_id = request.data.get("user_id")
            user = get_object_or_404(get_user_model(), id=user_id)

            # Validate participant limit
            if group.participants.count() >= settings.MAX_PARTICIPANTS_PER_GROUP:
                return Response(
                    {"error": "Maximum participant limit reached"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Add participant
            group.participants.add(user)

            # Send notifications
            notification_service.create_notification(
                user=user,
                message=f"You were added to group '{group.name}'",
                notification_type="group_update",
                url=f"/groups/{group.id}/",
            )

            notification_service.create_group_notification(
                group=group,
                message=f"{user.username} joined the group",
                exclude_users=[user],
            )

            return Response(
                {"message": f"Added {user.username} to group"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error adding participant: {str(e)}")
            return Response(
                {"error": "Failed to add participant"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def remove_participant(self, request, pk=None):
        """Remove participant with proper validation"""
        try:
            group = self.get_object()
            user_id = request.data.get("user_id")
            user = get_object_or_404(get_user_model(), id=user_id)

            # Validate permissions
            if not (
                request.user.id == user_id  # Self-removal
                or group.moderators.filter(id=request.user.id).exists()  # Moderator
            ):
                return Response(
                    {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
                )

            # Remove from both participants and moderators
            group.participants.remove(user)
            group.moderators.remove(user)

            # Send notifications
            notification_service.create_notification(
                user=user,
                message=f"You were removed from group '{group.name}'",
                notification_type="group_update",
            )

            notification_service.create_group_notification(
                group=group,
                message=f"{user.username} left the group",
                exclude_users=[user],
            )

            return Response(
                {"message": f"Removed {user.username} from group"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error removing participant: {str(e)}")
            return Response(
                {"error": "Failed to remove participant"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def pin_message(self, request, pk=None):
        group = self.get_object()
        # Check that the current user is a moderator
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "Only moderators can pin messages"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Pinning logic: For example, set a pinned_message field or mark a message as pinned.
        pinned_message_id = request.data.get("message_id")
        if not pinned_message_id:
            return Response(
                {"detail": "Message ID is required to pin a message."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Here, you could implement your pinning mechanism.
        # For demonstration, we update a hypothetical `pinned_message` field on the group.
        group.pinned_message_id = pinned_message_id
        group.save()

        # Send notifications to group participants except the request.user
        notification_service.create_group_notification(
            group=group,
            message=f"Message {pinned_message_id} has been pinned by {request.user.username}",
            exclude_users=[request.user],
        )

        return Response(
            {"detail": "Message pinned successfully."}, status=status.HTTP_200_OK
        )

    @extend_schema(exclude=True)
    @action(detail=False, methods=["post"])  # or detail=True, depending on your needs
    def create_anonymous(self, request):
        # ... your logic here ...
        return Response({"status": "success"})


class GroupMessageViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomMessagePagination

    def get_queryset(self):
        """
        Returns messages from groups where user is a participant,
        with optimized queries
        """
        return (
            GroupMessage.objects.filter(conversation__participants=self.request.user)
            .select_related("sender", "conversation")
            .prefetch_related(
                Prefetch("conversation__participants"), Prefetch("read_by")
            )
            .order_by("-timestamp")
        )

    def perform_create(self, serializer):
        try:
            conversation_id = serializer.validated_data.get("conversation")
            conversation = GroupConversation.objects.get(id=conversation_id.id)

            # Check permissions
            if not conversation.participants.filter(id=self.request.user.id).exists():
                raise ValidationError("You are not a participant in this conversation.")

            message = serializer.save(
                sender=self.request.user, conversation=conversation
            )

            # Send notifications to group members
            create_group_notifications.delay(
                message.conversation.id,
                f"New message from {self.request.user.username}",
                exclude_users=[self.request.user],
            )

            return message

        except GroupConversation.DoesNotExist:
            raise ValidationError(f"Conversation {conversation_id} does not exist.")
        except Exception as e:
            logger.error(f"Error creating message: {str(e)}")
            raise ValidationError(str(e))

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if (
            instance.sender != request.user
            and not instance.conversation.moderators.filter(id=request.user.id).exists()
        ):
            return Response(
                {"detail": "You do not have permission to edit this message."},
                status=status.HTTP_403_FORBIDDEN,
            )

        response = super().update(request, *args, **kwargs)

        # Notify participants of message edit
        notification_service.create_group_notification(
            group=instance.conversation,
            message=f"Message edited by {request.user.username}",
            exclude_users=[request.user],
            url=f"/groups/{instance.conversation.id}/messages/{instance.id}/",
        )

        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if (
            instance.sender != request.user
            and not instance.conversation.moderators.filter(id=request.user.id).exists()
        ):
            return Response(
                {"detail": "You do not have permission to delete this message."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Notify participants of message deletion
        notification_service.create_group_notification(
            group=instance.conversation,
            message=f"Message deleted by {request.user.username}",
            exclude_users=[request.user],
        )

        return super().destroy(request, *args, **kwargs)
