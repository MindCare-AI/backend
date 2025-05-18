# messaging/mixins/reactions.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
import logging

logger = logging.getLogger(__name__)


class ReactionMixin:
    """Mixin to add reaction functionality to message viewsets"""

    @extend_schema(
        description="Add a reaction to a message",
        summary="Add Reaction",
        tags=["Message"],
        request={"type": "object", "properties": {"reaction": {"type": "string"}}},
        responses={
            200: {"description": "Reaction added successfully"},
            400: {"description": "Bad Request"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["post"], url_path="add-reaction")
    def add_reaction(self, request, pk=None):
        """Add a reaction to a specific message."""
        try:
            # Get the message
            message = self.get_object()

            # Get the reaction from request data
            reaction_type = request.data.get("reaction")
            if not reaction_type:
                return Response(
                    {"error": "Reaction type is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Add the reaction
            if not hasattr(message, "add_reaction"):
                return Response(
                    {"error": "This message does not support reactions."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Store the user who added this reaction for notification purposes
            message._last_reactor = request.user
            message._last_reaction_type = reaction_type

            # Add the reaction
            message.add_reaction(request.user, reaction_type)

            # Return the updated message
            serializer = self.get_serializer(message)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error adding reaction: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Remove a reaction from a message",
        summary="Remove Reaction",
        tags=["Message"],
        request={"type": "object", "properties": {"reaction": {"type": "string"}}},
        responses={
            200: {"description": "Reaction removed successfully"},
            400: {"description": "Bad Request"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["delete"], url_path="remove-reaction")
    def remove_reaction(self, request, pk=None):
        """Remove a reaction from a specific message."""
        try:
            # Get the message
            message = self.get_object()

            # Get the reaction from request data
            reaction_type = request.data.get("reaction")
            if not reaction_type:
                return Response(
                    {"error": "Reaction type is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if message supports reactions
            if not hasattr(message, "remove_reaction"):
                return Response(
                    {"error": "This message does not support reactions."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Remove the reaction
            if (
                reaction_type in message.reactions
                and request.user.id in message.reactions[reaction_type]
            ):
                message.remove_reaction(request.user)

                # Return the updated message
                serializer = self.get_serializer(message)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Reaction not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            logger.error(f"Error removing reaction: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Get all reactions for a message",
        summary="Get Reactions",
        tags=["Message"],
        responses={
            200: {"description": "Reactions retrieved successfully"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["get"], url_path="reactions")
    def get_reactions(self, request, pk=None):
        """Get all reactions for a specific message."""
        try:
            # Get the message
            message = self.get_object()

            # Check if message has reactions
            if not hasattr(message, "reactions"):
                return Response(
                    {"error": "This message does not support reactions."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get the reactions
            reactions = message.reactions

            # Enhance reaction data with user information
            enhanced_reactions = {}
            from django.contrib.auth import get_user_model

            User = get_user_model()

            for reaction_type, user_ids in reactions.items():
                users = User.objects.filter(id__in=user_ids).values("id", "username")
                enhanced_reactions[reaction_type] = list(users)

            return Response(enhanced_reactions, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting reactions: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
