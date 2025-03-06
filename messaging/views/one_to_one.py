# messaging/views/one_to_one.py
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
    OneToOneMessageSerializer,
)


class OneToOneConversationViewSet(viewsets.ModelViewSet):
    queryset = OneToOneConversation.objects.all()
    serializer_class = OneToOneConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(participants=self.request.user)

    def perform_create(self, serializer):
        """Ensure that the creator is added to participants"""
        try:
            with transaction.atomic():
                instance = serializer.save()
                # Add the current user to participants if not already added
                instance.participants.add(self.request.user)
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
        except IntegrityError as e:
            raise ValidationError(f"Failed to update conversation: {str(e)}")
        except DjangoValidationError as e:
            raise ValidationError(f"Validation error: {str(e)}")


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
            conversation_id = serializer.validated_data.get("conversation")
            if conversation_id:
                try:
                    OneToOneConversation.objects.get(
                        id=conversation_id.id, participants=request.user
                    )
                except OneToOneConversation.DoesNotExist:
                    return Response(
                        {
                            "detail": "Conversation not found or you are not a participant."
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Save with current user as sender
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                    status=status.HTTP_403_FORBIDDEN,
                )

            return super().update(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
