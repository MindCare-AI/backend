#messaging/views/one_to_one.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from django.db.models import Count, Max, Q, Prefetch

from ..models.one_to_one import OneToOneConversation, OneToOneMessage
from ..serializers.one_to_one import (
    OneToOneConversationSerializer,
    OneToOneMessageSerializer
)

class OneToOneConversationViewSet(viewsets.ModelViewSet):
    queryset = OneToOneConversation.objects.all()
    serializer_class = OneToOneConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Get conversations that the current user is part of,
        with annotations for latest message info and unread count
        """
        user = self.request.user
        
        # Prefetch recent messages for each conversation to avoid N+1 queries
        message_prefetch = Prefetch(
            'messages',
            queryset=OneToOneMessage.objects.order_by('-timestamp')[:5],
            to_attr='recent_messages'
        )
        
        # Get all conversations with additional useful data
        return self.queryset.filter(participants=user)\
            .prefetch_related('participants', message_prefetch)\
            .annotate(
                last_message_time=Max('messages__timestamp'),
                unread_count=Count(
                    'messages',
                    filter=~Q(messages__read_by=user) & ~Q(messages__sender=user)
                )
            ).order_by('-last_message_time')
    
    def list(self, request, *args, **kwargs):
        """Enhanced list response with additional data"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Add pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                response_data = self.enrich_conversation_data(serializer.data)
                return self.get_paginated_response(response_data)
            
            serializer = self.get_serializer(queryset, many=True)
            response_data = self.enrich_conversation_data(serializer.data)
            return Response(response_data)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def enrich_conversation_data(self, data):
        """Add additional info to conversation data for the UI"""
        user = self.request.user
        
        for conversation_data in data:
            conversation_id = conversation_data['id']
            conversation = OneToOneConversation.objects.get(id=conversation_id)
            
            # Get other participant's info
            other_participants = conversation.participants.exclude(id=user.id)
            conversation_data['other_participants'] = [
                {
                    'id': participant.id,
                    'username': participant.username,
                    'first_name': participant.first_name,
                    'last_name': participant.last_name,
                    'email': participant.email,
                    # Add any other user fields you want to include
                }
                for participant in other_participants
            ]
            
            # Get latest message preview
            latest_messages = getattr(conversation, 'recent_messages', [])
            if latest_messages:
                latest_message = latest_messages[0]
                conversation_data['latest_message'] = {
                    'id': latest_message.id,
                    'content': latest_message.content[:100] + ('...' if len(latest_message.content) > 100 else ''),
                    'timestamp': latest_message.timestamp,
                    'is_from_current_user': latest_message.sender_id == user.id,
                    'sender_name': latest_message.sender.get_full_name() or latest_message.sender.username,
                }
        
        return data
    
    def retrieve(self, request, *args, **kwargs):
        """Enhanced detail view with messages"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            
            # Get conversation data
            response_data = serializer.data
            
            # Add other participant info
            other_participants = instance.participants.exclude(id=request.user.id)
            response_data['other_participants'] = [
                {
                    'id': participant.id,
                    'username': participant.username,
                    'first_name': participant.first_name,
                    'last_name': participant.last_name,
                    'email': participant.email,
                }
                for participant in other_participants
            ]
            
            # Get recent messages (limit to last 20)
            messages = instance.messages.all().order_by('-timestamp')[:20]
            message_serializer = OneToOneMessageSerializer(messages, many=True)
            response_data['messages'] = message_serializer.data
            
            # Mark messages as read
            unread_messages = messages.exclude(sender=request.user).exclude(read_by=request.user)
            for message in unread_messages:
                message.read_by.add(request.user)
            
            return Response(response_data)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        """Ensure that the creator is added to participants"""
        try:
            with transaction.atomic():
                instance = serializer.save()
                # Add the current user to participants if not already added
                instance.participants.add(self.request.user)
                
                # Validate that the conversation has exactly two participants
                if 'participants' in serializer.validated_data:
                    if instance.participants.count() != 2:
                        raise ValidationError("One-to-one conversations must have exactly two participants.")
        except IntegrityError as e:
            raise ValidationError(f"Failed to create conversation: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")
    
    def perform_update(self, serializer):
        """Ensure that the current user remains a participant"""
        try:
            with transaction.atomic():
                instance = serializer.save()
                # Make sure the current user is still a participant
                if self.request.user not in instance.participants.all():
                    instance.participants.add(self.request.user)
                    
                # Validate that the conversation still has exactly two participants
                if instance.participants.count() != 2:
                    raise ValidationError("One-to-one conversations must have exactly two participants.")
        except IntegrityError as e:
            raise ValidationError(f"Failed to update conversation: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")
            
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a specific conversation with pagination"""
        try:
            conversation = self.get_object()
            
            # Get query parameters for pagination
            page_size = int(request.query_params.get('page_size', 20))
            before_id = request.query_params.get('before_id')
            after_id = request.query_params.get('after_id')
            
            # Base query
            messages = conversation.messages.all()
            
            # Apply cursor-based pagination
            if before_id:
                before_message = OneToOneMessage.objects.get(id=before_id)
                messages = messages.filter(timestamp__lt=before_message.timestamp)
            
            if after_id:
                after_message = OneToOneMessage.objects.get(id=after_id)
                messages = messages.filter(timestamp__gt=after_message.timestamp)
                
            # Order and limit
            messages = messages.order_by('-timestamp')[:page_size]
            
            # Serialize
            serializer = OneToOneMessageSerializer(messages, many=True)
            
            # Mark as read
            unread_messages = messages.exclude(sender=request.user).exclude(read_by=request.user)
            for message in unread_messages:
                message.read_by.add(request.user)
                
            return Response({
                'results': serializer.data,
                'has_more': messages.count() == page_size
            })
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OneToOneMessageViewSet(viewsets.ModelViewSet):
    queryset = OneToOneMessage.objects.all()
    serializer_class = OneToOneMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(conversation__participants=self.request.user)
    
    def create(self, request, *args, **kwargs):
        try:
            # Ensure sender is set to current user
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Verify the conversation exists and user is a participant
            conversation_id = serializer.validated_data.get('conversation')
            if conversation_id:
                try:
                    conversation = OneToOneConversation.objects.get(
                        id=conversation_id.id, 
                        participants=request.user
                    )
                except OneToOneConversation.DoesNotExist:
                    return Response(
                        {"detail": "Conversation not found or you are not a participant."},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Save with current user as sender
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        """Set the current user as the sender of the message"""
        try:
            serializer.save(sender=self.request.user)
        except IntegrityError as e:
            raise ValidationError(f"Failed to create message: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")
    
    def update(self, request, *args, **kwargs):
        """Only allow updating if user is the sender"""
        try:
            instance = self.get_object()
            if instance.sender != request.user:
                return Response(
                    {"detail": "You can only edit messages you've sent."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return super().update(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_update(self, serializer):
        """Prevent changing the sender"""
        try:
            # Ensure sender remains the same
            serializer.save(sender=serializer.instance.sender)
        except IntegrityError as e:
            raise ValidationError(f"Failed to update message: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")