# messaging/mixins/reactions.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from drf_spectacular.utils import extend_schema
import logging

logger = logging.getLogger(__name__)


class ReactionMixin:
    """Mixin to add reaction functionality to message viewsets"""

    @extend_schema(
        summary="Add Reaction",
        description="Add or update a reaction to a message. Valid reactions include: like, heart, smile, thumbsup.",
        request={
            "type": "object",
            "properties": {"reaction": {"type": "string", "example": "like"}},
            "required": ["reaction"],
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                    "reactions": {"type": "object"},
                },
            },
            400: {"description": "Bad Request"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["post"])
    def add_reaction(self, request, pk=None):
        """Add or update a reaction to a message"""
        try:
            try:
                message = self.get_object()
            except Http404:
                return Response(
                    {"error": f"Message with ID {pk} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            reaction_type = request.data.get("reaction")

            if not reaction_type:
                return Response(
                    {"error": "Reaction type is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate reaction type
            valid_reactions = {"like", "heart", "smile", "thumbsup"}
            if reaction_type not in valid_reactions:
                return Response(
                    {
                        "error": f'Invalid reaction type. Must be one of: {", ".join(valid_reactions)}'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Initialize reactions dict if needed
            if not message.reactions:
                message.reactions = {}
            if reaction_type not in message.reactions:
                message.reactions[reaction_type] = []

            # Store user ID as string for JSON serialization (consistent format)
            user_id = str(request.user.id)
            if user_id not in message.reactions[reaction_type]:
                # Store reference to last reactor for signal notification
                message._last_reactor = request.user
                message.last_reaction_type = reaction_type

                # Add user to reaction list
                message.reactions[reaction_type].append(user_id)
                message.save()

            return Response(
                {
                    "status": "success",
                    "message": f"Added reaction {reaction_type}",
                    "reactions": message.reactions,
                }
            )

        except Exception as e:
            logger.error(f"Error adding reaction: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to add reaction"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Remove Reaction",
        description="Remove a user's reaction from a message.",
        request={
            "type": "object",
            "properties": {"reaction": {"type": "string", "example": "like"}},
            "required": ["reaction"],
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                    "reactions": {"type": "object"},
                },
            },
            400: {"description": "Bad Request"},
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["delete"])
    def remove_reaction(self, request, pk=None):
        """Remove a user's reaction from a message"""
        try:
            try:
                message = self.get_object()
            except Http404:
                return Response(
                    {"error": f"Message with ID {pk} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            reaction_type = request.data.get("reaction")

            if not reaction_type:
                return Response(
                    {"error": "Reaction type is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not message.reactions or reaction_type not in message.reactions:
                return Response(
                    {"error": "No reactions to remove"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Remove user from reaction type - ensure consistent ID format
            user_id = str(request.user.id)
            if user_id in message.reactions[reaction_type]:
                message.reactions[reaction_type].remove(user_id)
                # Clean up empty reaction types
                if not message.reactions[reaction_type]:
                    del message.reactions[reaction_type]
                message.save()

            return Response(
                {
                    "status": "success",
                    "message": "Reaction removed",
                    "reactions": message.reactions,
                }
            )

        except Exception as e:
            logger.error(f"Error removing reaction: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to remove reaction"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="List Reactions",
        description="Get all reactions for a message.",
        responses={
            200: {
                "type": "object",
                "properties": {"reactions": {"type": "object"}},
            },
            404: {"description": "Message not found"},
            500: {"description": "Internal Server Error"},
        },
    )
    @action(detail=True, methods=["get"])
    def reactions(self, request, pk=None):
        """Get all reactions for a message"""
        try:
            try:
                message = self.get_object()
            except Http404:
                return Response(
                    {"error": f"Message with ID {pk} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(message.reactions or {})

        except Exception as e:
            logger.error(f"Error fetching reactions: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to fetch reactions"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
