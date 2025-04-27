# messaging/caches/offline_handler.py
import logging
import time
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .cache_manager import message_cache
from ..models.one_to_one import OneToOneMessage, OneToOneConversation
from ..models.group import GroupMessage, GroupConversation
from ..models.chatbot import ChatbotMessage, ChatbotConversation

User = get_user_model()
logger = logging.getLogger(__name__)

class OfflineMessageHandler:
    """
    Handles synchronization of messages created while offline.
    
    This class manages:
    - Processing queued offline messages when connection is restored
    - Creating database records from cached message data
    - Handling conflict resolution for messages created while offline
    """
    
    def __init__(self):
        # Map conversation types to their message models
        self.message_models = {
            "OneToOneConversation": OneToOneMessage,
            "GroupConversation": GroupMessage,
            "ChatbotConversation": ChatbotMessage,
        }
        
        # Map conversation types to their conversation models
        self.conversation_models = {
            "OneToOneConversation": OneToOneConversation,
            "GroupConversation": GroupConversation,
            "ChatbotConversation": ChatbotConversation,
        }
    
    def sync_offline_messages(self, user_id: int) -> Dict[str, Any]:
        """
        Process all offline messages for a user and persist them to the database.
        
        Args:
            user_id: The user ID whose offline messages should be synced
            
        Returns:
            Dict with results of the sync operation, including success count, error count, and errors
        """
        try:
            # Get all queued messages
            offline_queue = message_cache.get_offline_queue(user_id)
            if not offline_queue:
                return {"success_count": 0, "error_count": 0, "already_synced": 0, "errors": []}
                
            logger.info(f"Processing {len(offline_queue)} offline messages for user {user_id}")
            
            result = {
                "success_count": 0,
                "error_count": 0,
                "already_synced": 0,
                "errors": []
            }
            
            successful_ids = []
            
            # Process each message
            for message_data in offline_queue:
                if message_data.get('status') == 'sent':
                    result["already_synced"] += 1
                    continue
                    
                try:
                    # Process the message and get the result
                    success, new_message_id, error_msg = self._process_offline_message(message_data, user_id)
                    
                    if success:
                        result["success_count"] += 1
                        successful_ids.append(message_data.get('id'))
                        
                        # Update message data with new database ID
                        message_data['db_id'] = new_message_id
                        message_data['status'] = 'sent'
                        message_data['sent_at'] = time.time()
                    else:
                        result["error_count"] += 1
                        result["errors"].append({
                            "message_id": message_data.get('id'),
                            "error": error_msg
                        })
                except Exception as e:
                    logger.error(f"Error processing offline message: {str(e)}", exc_info=True)
                    result["error_count"] += 1
                    result["errors"].append({
                        "message_id": message_data.get('id'),
                        "error": str(e)
                    })
            
            # Mark successful messages as sent
            if successful_ids:
                message_cache.mark_offline_messages_sent(user_id, successful_ids)
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to sync offline messages for user {user_id}: {str(e)}", exc_info=True)
            return {
                "success_count": 0,
                "error_count": 1,
                "errors": [{"error": f"Sync failed: {str(e)}"}]
            }
    
    @transaction.atomic
    def _process_offline_message(self, message_data: Dict[str, Any], user_id: int) -> tuple:
        """
        Process a single offline message and persist it to the database.
        
        Args:
            message_data: The cached message data
            user_id: The user ID who created the message
            
        Returns:
            Tuple of (success, new_message_id, error_message)
        """
        try:
            # Get required data
            conversation_id = message_data.get('conversation_id')
            content = message_data.get('content')
            message_type = message_data.get('message_type', 'text')
            
            if not conversation_id or not content:
                return False, None, "Missing required message data"
            
            # Get the conversation
            conversation_data = message_cache.get_cached_conversation(conversation_id)
            if not conversation_data:
                return False, None, f"Conversation {conversation_id} not found in cache"
                
            # Determine conversation type and get appropriate model
            conversation_type = conversation_data.get('type')
            if not conversation_type or conversation_type not in self.message_models:
                return False, None, f"Invalid conversation type: {conversation_type}"
                
            # Get conversation from database
            conversation_model = self.conversation_models[conversation_type]
            try:
                conversation = conversation_model.objects.get(id=conversation_id)
            except conversation_model.DoesNotExist:
                return False, None, f"Conversation {conversation_id} not found in database"
                
            # Check if user is a participant
            if not self._is_user_participant(conversation, user_id):
                return False, None, "User is not a participant in this conversation"
                
            # Get user instance
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return False, None, f"User {user_id} not found"
                
            # Create the message
            message_model = self.message_models[conversation_type]
            message = message_model(
                conversation=conversation,
                sender=user,
                content=content,
                message_type=message_type,
                metadata=message_data.get('metadata', {}),
                timestamp=timezone.now()
            )
            
            # Set any additional fields based on the conversation type
            if conversation_type == 'ChatbotConversation':
                message.is_bot = False
            
            message.save()
            
            # Update conversation last activity
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=['last_activity'])
            
            # Cache the new message
            message_cache.cache_message(message)
            
            return True, message.id, None
            
        except Exception as e:
            logger.error(f"Error processing offline message: {str(e)}", exc_info=True)
            return False, None, str(e)
    
    def _is_user_participant(self, conversation, user_id: int) -> bool:
        """
        Check if user is a participant in the conversation.
        
        Args:
            conversation: The conversation object
            user_id: The user ID to check
            
        Returns:
            bool: True if user is a participant, False otherwise
        """
        if hasattr(conversation, 'participants'):
            return conversation.participants.filter(id=user_id).exists()
        elif hasattr(conversation, 'user') and hasattr(conversation.user, 'id'):
            return conversation.user.id == user_id
        return False
    
    def clear_synced_messages(self, user_id: int) -> bool:
        """
        Clear synced messages from the offline queue.
        
        Args:
            user_id: The user ID whose synced messages should be cleared
            
        Returns:
            bool: Success status
        """
        try:
            # Get all queued messages
            offline_queue = message_cache.get_offline_queue(user_id)
            if not offline_queue:
                return True
                
            # Filter to keep only non-synced messages
            new_queue = [msg for msg in offline_queue if msg.get('status') != 'sent']
            
            # If the queue changed, update it
            if len(new_queue) != len(offline_queue):
                queue_key = f"{message_cache.OFFLINE_QUEUE_PREFIX}{user_id}"
                message_cache.cache.set(queue_key, new_queue, message_cache.CONVERSATION_TIMEOUT)
                
            return True
        except Exception as e:
            logger.error(f"Error clearing synced messages for user {user_id}: {str(e)}")
            return False

# Create a singleton instance for use throughout the application
offline_handler = OfflineMessageHandler()