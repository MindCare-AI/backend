from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q, Prefetch
from django.contrib.auth import get_user_model
import logging

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, APIException

from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models.group import GroupConversation, GroupMessage
from ..serializers.group import GroupConversationSerializer, GroupMessageSerializer
from ..pagination import CustomMessagePagination

logger = logging.getLogger(__name__)

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
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(participants=self.request.user)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                instance = serializer.save()
                instance.participants.add(self.request.user)
                instance.moderators.add(self.request.user)
        except IntegrityError as e:
            raise ValidationError(f"Failed to create group conversation: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")

    @extend_schema(
        description="Add a user as a moderator to the group. The current user must be a moderator.",
        summary="Add Moderator",
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["post"])
    def add_moderator(self, request, pk=None):
        group = self.get_object()
        if not group.moderators.filter(id=request.user.id).exists():
            return Response({"detail": "You don't have permission to add moderators."}, status=status.HTTP_403_FORBIDDEN)
        user = get_object_or_404(get_user_model(), id=request.data.get("user_id"))
        if not group.participants.filter(id=user.id).exists():
            return Response({"detail": "User must be a participant before being promoted to moderator."}, status=status.HTTP_400_BAD_REQUEST)
        group.moderators.add(user)
        return Response({"detail": f"User {user.username} is now a moderator."}, status=status.HTTP_200_OK)

    @extend_schema(
        description="List all moderators of the group.",
        summary="List Moderators",
        tags=["Group Conversation"],
    )
    @action(detail=True, methods=["get"])
    def moderators(self, request, pk=None):
        group = self.get_object()
        moderator_data = [{
            "id": mod.id, "username": mod.username,
            "first_name": mod.first_name, "last_name": mod.last_name,
            "email": mod.email
        } for mod in group.moderators.all()]
        return Response(moderator_data)

class GroupMessageViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomMessagePagination

    def get_queryset(self):
        """
        Returns messages from groups where user is a participant,
        with optimized queries
        """
        return (GroupMessage.objects
                .filter(conversation__participants=self.request.user)
                .select_related('sender', 'conversation')
                .prefetch_related(
                    Prefetch('conversation__participants'),
                    Prefetch('read_by')
                )
                .order_by('-timestamp'))

    def list(self, request, *args, **kwargs):
        """Enhanced list view with group context"""
        queryset = self.get_queryset()
        
        # Check if user is in any groups
        if not GroupConversation.objects.filter(participants=request.user).exists():
            return Response({
                'detail': 'You are not a member of any group conversations.',
                'results': [],
                'count': 0
            }, status=status.HTTP_200_OK)

        # Get paginated results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            # Add group context
            response.data['user_groups'] = self.get_user_groups(request.user)
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_user_groups(self, user):
        """Helper method to get user's groups information"""
        groups = GroupConversation.objects.filter(participants=user)
        return [{
            'id': group.id,
            'name': group.name,
            'participant_count': group.participants.count(),
            'is_moderator': group.moderators.filter(id=user.id).exists()
        } for group in groups]

    def perform_create(self, serializer):
        try:
            conversation_id = serializer.validated_data.get('conversation')
            
            # Debug logging
            logger.debug(f"Creating message for conversation {conversation_id}")
            logger.debug(f"Current user: {self.request.user.id}")
            
            conversation = GroupConversation.objects.get(id=conversation_id.id)
            
            # Explicitly check permissions
            is_participant = conversation.participants.filter(id=self.request.user.id).exists()
            is_moderator = conversation.moderators.filter(id=self.request.user.id).exists()
            
            logger.debug(f"Is participant: {is_participant}")
            logger.debug(f"Is moderator: {is_moderator}")

            if not is_participant:
                raise ValidationError("You are not a participant in this conversation.")

            message = serializer.save(
                sender=self.request.user,
                conversation=conversation
            )
            
            return message

        except GroupConversation.DoesNotExist:
            raise ValidationError(f"Conversation {conversation_id} does not exist.")
        except Exception as e:
            logger.error(f"Error creating message: {str(e)}")
            raise ValidationError(str(e))

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.sender != request.user and not instance.conversation.moderators.filter(id=request.user.id).exists():
            return Response({"detail": "You do not have permission to edit this message."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.sender != request.user and not instance.conversation.moderators.filter(id=request.user.id).exists():
            return Response({"detail": "You do not have permission to delete this message."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)
