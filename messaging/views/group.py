#messaging/views/group.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from ..models.group import GroupConversation, GroupMessage
from ..serializers.group import (
    GroupConversationSerializer,
    GroupMessageSerializer
)

class GroupConversationViewSet(viewsets.ModelViewSet):
    queryset = GroupConversation.objects.all()
    serializer_class = GroupConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(participants=self.request.user)
    
    def perform_create(self, serializer):
        """
        Create a group conversation and set the creator as both 
        a participant and moderator automatically
        """
        try:
            with transaction.atomic():
                # Create the conversation
                instance = serializer.save()
                
                # Add the creator as a participant
                instance.participants.add(self.request.user)
                
                # Add the creator as a moderator
                instance.moderators.add(self.request.user)
                
        except IntegrityError as e:
            raise ValidationError(f"Failed to create group conversation: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")
    
    @action(detail=True, methods=['post'])
    def add_moderator(self, request, pk=None):
        """Add a user as moderator to the group"""
        group = self.get_object()
        
        # Check if the current user is a moderator
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "You don't have permission to add moderators."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user to add as moderator
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {"detail": "User ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Check if user is a participant
            if not group.participants.filter(id=user.id).exists():
                return Response(
                    {"detail": "User must be a participant before being promoted to moderator."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Add as moderator
            group.moderators.add(user)
            
            return Response(
                {"detail": f"User {user.username} is now a moderator."},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def remove_moderator(self, request, pk=None):
        """Remove moderator status from a user"""
        group = self.get_object()
        
        # Check if the current user is a moderator
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "You don't have permission to remove moderators."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user to remove from moderators
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {"detail": "User ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Prevent removing the last moderator
            if group.moderators.count() <= 1 and group.moderators.filter(id=user.id).exists():
                return Response(
                    {"detail": "Cannot remove the last moderator."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Remove moderator status
            group.moderators.remove(user)
            
            return Response(
                {"detail": f"User {user.username} is no longer a moderator."},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def moderators(self, request, pk=None):
        """List all moderators of the group"""
        group = self.get_object()
        
        moderators = group.moderators.all()
        
        # Format moderator information
        moderator_data = [
            {
                'id': moderator.id,
                'username': moderator.username,
                'first_name': moderator.first_name,
                'last_name': moderator.last_name,
                'email': moderator.email,
            }
            for moderator in moderators
        ]
        
        return Response(moderator_data)
    
    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """Add participant to the group (moderator only)"""
        group = self.get_object()
        
        # Check if the current user is a moderator
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "Only moderators can add participants."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user to add
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {"detail": "User ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Add as participant
            group.participants.add(user)
            
            # Create system message
            GroupMessage.objects.create(
                content=f"{user.username} has joined the group",
                sender=request.user,
                conversation=group,
                message_type='system'
            )
            
            return Response(
                {"detail": f"User {user.username} added to the group."},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def remove_participant(self, request, pk=None):
        """Remove participant from the group (moderator only)"""
        group = self.get_object()
        
        # Check if the current user is a moderator
        if not group.moderators.filter(id=request.user.id).exists():
            return Response(
                {"detail": "Only moderators can remove participants."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user to remove
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {"detail": "User ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # If user is a moderator, remove their moderator status first
            if group.moderators.filter(id=user.id).exists():
                # Check if they're the last moderator
                if group.moderators.count() <= 1:
                    return Response(
                        {"detail": "Cannot remove the last moderator from the group."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                group.moderators.remove(user)
            
            # Remove from participants
            group.participants.remove(user)
            
            # Create system message
            GroupMessage.objects.create(
                content=f"{user.username} has been removed from the group",
                sender=request.user,
                conversation=group,
                message_type='system'
            )
            
            return Response(
                {"detail": f"User {user.username} removed from the group."},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GroupMessageViewSet(viewsets.ModelViewSet):
    queryset = GroupMessage.objects.all()
    serializer_class = GroupMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(conversation__participants=self.request.user)
    
    def perform_create(self, serializer):
        """Set the sender to the current user"""
        try:
            # Check if the user is a participant in the conversation
            conversation = serializer.validated_data.get('conversation')
            if not conversation.participants.filter(id=self.request.user.id).exists():
                raise ValidationError("You must be a participant to send messages in this group.")
            
            serializer.save(sender=self.request.user)
        except IntegrityError as e:
            raise ValidationError(f"Failed to create message: {str(e)}")
        except Exception as e:
            raise ValidationError(f"Error: {str(e)}")
    
    def update(self, request, *args, **kwargs):
        """Only allow message update by sender or moderator"""
        message = self.get_object()
        conversation = message.conversation
        
        # Check if user is the sender or a moderator
        is_sender = message.sender == request.user
        is_moderator = conversation.moderators.filter(id=request.user.id).exists()
        
        if not (is_sender or is_moderator):
            return Response(
                {"detail": "You don't have permission to edit this message."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Only allow message deletion by sender or moderator"""
        message = self.get_object()
        conversation = message.conversation
        
        # Check if user is the sender or a moderator
        is_sender = message.sender == request.user
        is_moderator = conversation.moderators.filter(id=request.user.id).exists()
        
        if not (is_sender or is_moderator):
            return Response(
                {"detail": "You don't have permission to delete this message."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)