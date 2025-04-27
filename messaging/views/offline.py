# messaging/views/offline.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..caches.service_cache import message_service_cache
from ..throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiResponse

import logging

logger = logging.getLogger(__name__)

class OfflineMessageSyncView(APIView):
    """
    Synchronize offline messages when a user comes back online.
    
    This endpoint handles:
    - Processing queued offline messages
    - Syncing with the database
    - Reporting success/failure stats
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @extend_schema(
        summary="Synchronize offline messages",
        description="Process and persist messages that were created while offline",
        responses={
            200: OpenApiResponse(description="Messages successfully synced"),
            400: OpenApiResponse(description="Invalid request"),
            401: OpenApiResponse(description="Unauthorized"),
            500: OpenApiResponse(description="Server error during sync"),
        },
        tags=["messaging"]
    )
    def post(self, request):
        """Process messages that were created while the user was offline."""
        try:
            user_id = request.user.id
            
            # Process offline messages
            sync_result = message_service_cache.process_offline_messages(user_id)
            
            if sync_result["success_count"] > 0 or sync_result["already_synced"] > 0:
                return Response({
                    "status": "success",
                    "message": f"Successfully synced {sync_result['success_count']} messages",
                    "synced_count": sync_result["success_count"],
                    "already_synced": sync_result["already_synced"],
                    "errors": sync_result["errors"] if sync_result["error_count"] > 0 else []
                }, status=status.HTTP_200_OK)
            elif sync_result["error_count"] > 0:
                return Response({
                    "status": "partial_success",
                    "message": f"Encountered {sync_result['error_count']} errors during sync",
                    "synced_count": sync_result["success_count"],
                    "already_synced": sync_result["already_synced"],
                    "errors": sync_result["errors"]
                }, status=status.HTTP_207_MULTI_STATUS)
            else:
                return Response({
                    "status": "success",
                    "message": "No offline messages to sync",
                    "synced_count": 0
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error during offline message sync: {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": "Failed to sync offline messages",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Get offline message queue status",
        description="Get information about queued offline messages",
        responses={
            200: OpenApiResponse(description="Queue status retrieved successfully"),
            401: OpenApiResponse(description="Unauthorized"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["messaging"]
    )
    def get(self, request):
        """Get information about queued offline messages."""
        try:
            user_id = request.user.id
            
            # Get offline queue
            offline_queue = message_service_cache.message_cache.get_offline_messages(user_id)
            
            # Count messages by status
            queued_count = 0
            sent_count = 0
            
            for msg in offline_queue:
                if msg.get('status') == 'sent':
                    sent_count += 1
                else:
                    queued_count += 1
            
            return Response({
                "status": "success",
                "queue_length": len(offline_queue),
                "queued_count": queued_count,
                "sent_count": sent_count,
                "last_sync": request.user.last_login or request.user.date_joined
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error retrieving offline queue: {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": "Failed to retrieve offline queue",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Clear offline message queue",
        description="Clear the offline message queue for the current user",
        responses={
            200: OpenApiResponse(description="Queue cleared successfully"),
            401: OpenApiResponse(description="Unauthorized"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["messaging"]
    )
    def delete(self, request):
        """Clear the offline message queue."""
        try:
            user_id = request.user.id
            
            # Clear offline queue
            success = message_service_cache.message_cache.clear_offline_messages(user_id)
            
            if success:
                return Response({
                    "status": "success",
                    "message": "Offline message queue cleared"
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": "error",
                    "message": "Failed to clear offline message queue"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error clearing offline queue: {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": "Failed to clear offline queue",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)