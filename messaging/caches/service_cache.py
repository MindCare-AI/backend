# messaging/caches/service_cache.py
import logging
import time
from typing import Dict, List, Any, Optional, Union
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from .cache_manager import message_cache
from .offline_handler import offline_handler

logger = logging.getLogger(__name__)

class MessageServiceCache:
    """
    Service layer cache for messaging.
    
    This class provides high-level caching operations for message services:
    - Cached message retrieval with database fallback
    - Batch message loading and caching
    - Conversation management with caching
    - Offline message handling integration
    """
    
    def __init__(self):
        self.message_cache = message_cache
        self.offline_handler = offline_handler
        
    def get_message(self, message_id: int, message_model):
        """
        Get a message by ID with caching.
        
        Args:
            message_id: The message ID
            message_model: The message model class
            
        Returns:
            Message object or None
        """
        try:
            # Try to get from cache first
            cached_message = self.message_cache.get_cached_message(message_id)
            
            if cached_message:
                logger.debug(f"Cache hit for message {message_id}")
                return cached_message
            
            # Not in cache, get from database
            logger.debug(f"Cache miss for message {message_id}, fetching from DB")
            message = message_model.objects.get(id=message_id)
            
            # Cache the message for next time
            self.message_cache.cache_message(message)
            
            return message
            
        except ObjectDoesNotExist:
            logger.warning(f"Message {message_id} not found in database")
            return None
        except Exception as e:
            logger.error(f"Error retrieving message {message_id}: {str(e)}")
            # Fall back to database directly on cache error
            try:
                return message_model.objects.get(id=message_id)
            except Exception:
                return None
    
    def get_messages_for_conversation(
        self, 
        conversation_id: int, 
        message_model, 
        limit: int = 50, 
        before_id: int = None,
        after_id: int = None
    ) -> List[Any]:
        """
        Get messages for a conversation with caching.
        
        Args:
            conversation_id: The conversation ID
            message_model: The message model class
            limit: Maximum number of messages to return
            before_id: Get messages before this ID
            after_id: Get messages after this ID
            
        Returns:
            List of message objects
        """
        try:
            # Check if we have a cached batch that might satisfy this request
            cached_batch = self.message_cache.get_cached_message_batch(conversation_id)
            
            # Try to use cached batch if it exists and we're not doing pagination
            if cached_batch and not before_id and not after_id:
                logger.debug(f"Using cached batch for conversation {conversation_id}")
                # Get message IDs sorted by timestamp (newest first)
                sorted_ids = sorted(
                    cached_batch.keys(), 
                    key=lambda k: cached_batch[k].get('timestamp', 0),
                    reverse=True
                )
                
                # Limit to requested count
                sorted_ids = sorted_ids[:limit]
                
                # Get messages from batch
                return [cached_batch[msg_id] for msg_id in sorted_ids]
            
            # Need to fetch from database
            logger.debug(f"Fetching messages for conversation {conversation_id} from DB")
            
            # Build query
            query = Q(conversation_id=conversation_id)
            if before_id:
                query &= Q(id__lt=before_id)
            if after_id:
                query &= Q(id__gt=after_id)
                
            # Fetch messages
            messages = list(
                message_model.objects.filter(query)
                .order_by('-timestamp')
                .select_related('sender')
                .prefetch_related('read_by')
                [:limit]
            )
            
            # Cache this batch
            self.message_cache.cache_message_batch(conversation_id, messages)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages for conversation {conversation_id}: {str(e)}")
            # Fall back to database directly
            try:
                query = Q(conversation_id=conversation_id)
                if before_id:
                    query &= Q(id__lt=before_id)
                if after_id:
                    query &= Q(id__gt=after_id)
                    
                return list(
                    message_model.objects.filter(query)
                    .order_by('-timestamp')
                    [:limit]
                )
            except Exception:
                return []
    
    def get_conversation(self, conversation_id: int, conversation_model):
        """
        Get a conversation by ID with caching.
        
        Args:
            conversation_id: The conversation ID
            conversation_model: The conversation model class
            
        Returns:
            Conversation object or None
        """
        try:
            # Try to get from cache first
            cached_conversation = self.message_cache.get_cached_conversation(conversation_id)
            
            if cached_conversation:
                logger.debug(f"Cache hit for conversation {conversation_id}")
                return cached_conversation
            
            # Not in cache, get from database
            logger.debug(f"Cache miss for conversation {conversation_id}, fetching from DB")
            conversation = conversation_model.objects.get(id=conversation_id)
            
            # Cache the conversation for next time
            self.message_cache.cache_conversation(conversation)
            
            return conversation
            
        except ObjectDoesNotExist:
            logger.warning(f"Conversation {conversation_id} not found in database")
            return None
        except Exception as e:
            logger.error(f"Error retrieving conversation {conversation_id}: {str(e)}")
            # Fall back to database directly on cache error
            try:
                return conversation_model.objects.get(id=conversation_id)
            except Exception:
                return None
    
    def get_user_conversations(self, user_id: int, conversation_model):
        """
        Get all conversations for a user with caching.
        
        Args:
            user_id: The user ID
            conversation_model: The conversation model class
            
        Returns:
            List of conversation objects
        """
        try:
            # Check if we have cached conversation IDs for this user
            conversation_ids = self.message_cache.get_user_conversations(user_id)
            
            if conversation_ids:
                logger.debug(f"Using cached conversation IDs for user {user_id}")
                conversations = []
                # Get each conversation from cache or database
                for conv_id in conversation_ids:
                    conv = self.get_conversation(conv_id, conversation_model)
                    if conv:
                        conversations.append(conv)
                return conversations
            
            # No cached IDs, fetch from database
            logger.debug(f"Fetching conversations for user {user_id} from DB")
            conversations = list(
                conversation_model.objects.filter(participants=user_id)
                .select_related()
                .prefetch_related('participants')
                .order_by('-last_activity')
            )
            
            # Cache each conversation
            for conv in conversations:
                self.message_cache.cache_conversation(conv)
                
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting conversations for user {user_id}: {str(e)}")
            # Fall back to database directly
            try:
                return list(
                    conversation_model.objects.filter(participants=user_id)
                    .order_by('-last_activity')
                )
            except Exception:
                return []
    
    def process_offline_messages(self, user_id: int) -> Dict:
        """
        Process and persist any offline messages for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dict with results of sync operation
        """
        return self.offline_handler.sync_offline_messages(user_id)
    
    def queue_offline_message(
        self, user_id: int, conversation_id: int, content: str, message_type: str = "text"
    ) -> Dict:
        """
        Queue a message to be sent when the user comes back online.
        
        Args:
            user_id: The sender's user ID
            conversation_id: The conversation ID
            content: Message content
            message_type: Type of message
            
        Returns:
            Dict with status and message ID
        """
        try:
            # Generate a temporary ID for the message
            temp_id = f"offline_{int(time.time())}_{user_id}_{conversation_id}"
            
            # Create message data
            message_data = {
                'id': temp_id,
                'content': content,
                'sender_id': user_id,
                'conversation_id': conversation_id,
                'timestamp': time.time(),
                'message_type': message_type,
                'metadata': {'offline': True, 'queued_at': time.time()},
            }
            
            # Queue the message
            success = self.message_cache.queue_offline_message(
                user_id, conversation_id, message_data
            )
            
            if success:
                return {
                    'status': 'queued',
                    'message_id': temp_id,
                    'queued_at': message_data['metadata']['queued_at']
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Failed to queue message'
                }
                
        except Exception as e:
            logger.error(f"Error queueing offline message: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    @transaction.atomic
    def save_message(self, message_obj) -> bool:
        """
        Save a message to database and cache.
        
        Args:
            message_obj: Message object to save
            
        Returns:
            bool: Success status
        """
        try:
            # Save to database
            message_obj.save()
            
            # Cache the message
            self.message_cache.cache_message(message_obj)
            
            # Update conversation cache
            conversation = message_obj.conversation
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=['last_activity'])
            self.message_cache.cache_conversation(conversation)
            
            return True
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return False
    
    def update_message(self, message_obj, update_fields: List[str] = None) -> bool:
        """
        Update a message in database and cache.
        
        Args:
            message_obj: Message object to update
            update_fields: Fields to update
            
        Returns:
            bool: Success status
        """
        try:
            # Save to database
            if update_fields:
                message_obj.save(update_fields=update_fields)
            else:
                message_obj.save()
            
            # Update cache
            self.message_cache.cache_message(message_obj)
            
            return True
        except Exception as e:
            logger.error(f"Error updating message: {str(e)}")
            return False
    
    def invalidate_message(self, message_id: int) -> bool:
        """
        Invalidate a message in cache.
        
        Args:
            message_id: The message ID to invalidate
            
        Returns:
            bool: Success status
        """
        try:
            self.message_cache.invalidate_message(message_id)
            return True
        except Exception as e:
            logger.error(f"Error invalidating message cache: {str(e)}")
            return False

# Create a singleton instance for use throughout the application
message_service_cache = MessageServiceCache()