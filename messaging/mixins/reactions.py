from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

class ReactionMixin:
    """Mixin to add reaction functionality to message viewsets"""
    
    @action(detail=True, methods=['post'])
    def add_reaction(self, request, pk=None):
        """Add or update a reaction to a message"""
        try:
            message = self.get_object()
            reaction_type = request.data.get('reaction')
            
            if not reaction_type:
                return Response(
                    {'error': 'Reaction type is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate reaction type
            valid_reactions = {'like', 'heart', 'smile', 'thumbsup'}
            if reaction_type not in valid_reactions:
                return Response(
                    {'error': f'Invalid reaction type. Must be one of: {", ".join(valid_reactions)}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Add or update reaction
            message.add_reaction(request.user, reaction_type)
            
            return Response({
                'status': 'success',
                'message': f'Added reaction {reaction_type}',
                'reactions': message.reactions
            })

        except Exception as e:
            logger.error(f"Error adding reaction: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to add reaction'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def remove_reaction(self, request, pk=None):
        """Remove a user's reaction from a message"""
        try:
            message = self.get_object()
            message.remove_reaction(request.user)
            
            return Response({
                'status': 'success',
                'message': 'Reaction removed',
                'reactions': message.reactions
            })

        except Exception as e:
            logger.error(f"Error removing reaction: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to remove reaction'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def reactions(self, request, pk=None):
        """Get all reactions for a message"""
        try:
            message = self.get_object()
            return Response(message.reactions)
            
        except Exception as e:
            logger.error(f"Error fetching reactions: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to fetch reactions'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )