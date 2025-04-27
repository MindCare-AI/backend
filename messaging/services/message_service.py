from typing import Dict, List
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from ..caches.cache_manager import MessagingCacheManager
from ..models.base import BaseMessage
from ..models.one_to_one import OneToOneMessage
from ..models.group import GroupMessage
from ..exceptions import MessageDeliveryError

logger = logging.getLogger(__name__)

class MessageService:
    """Service class for handling message operations with caching"""
    
    def __init__(self):
        self.cache_manager = MessagingCacheManager()
        self.channel_layer = get_channel_layer()
    
    def get_message(self, message_id: str, message_type: str = None) -> Dict:
        """Get a message with caching"""
        # Try cache first
        cached_message = self.cache_manager.get_message(message_id)
        if cached_message:
            return cached_message
            
        # If not in cache, get from database
        try:
            if message_type == 'one_to_one':
                message = OneToOneMessage.objects.get(id=message_id)
            elif message_type == 'group':
                message = GroupMessage.objects.get(id=message_id)
            else:
                message = BaseMessage.objects.get(id=message_id)
                
            # Convert to dict and cache
            message_data = message.to_dict()
            self.cache_manager.set_message(message_id, message_data)
            return message_data
            
        except ObjectDoesNotExist:
            return None
    
    def get_conversation_messages(self, conversation_id: str) -> List[Dict]:
        """Get all messages for a conversation with caching"""
        # Try cache first
        cached_messages = self.cache_manager.get_conversation_messages(conversation_id)
        if cached_messages:
            return cached_messages
            
        # If not in cache, get from database
        messages = BaseMessage.objects.filter(conversation_id=conversation_id).order_by('created_at')
        message_list = [msg.to_dict() for msg in messages]
        
        # Cache the messages
        self.cache_manager.set_conversation_messages(conversation_id, message_list)
        return message_list
    
    def create_message(self, conversation_id: str, sender_id: str, content: str, 
                      message_type: str = 'one_to_one', **kwargs) -> Dict:
        """Create a new message with caching"""
        # Create message in database
        message_data = {
            'conversation_id': conversation_id,
            'sender_id': sender_id,
            'content': content,
            'created_at': timezone.now(),
            **kwargs
        }
        
        if message_type == 'one_to_one':
            message = OneToOneMessage.objects.create(**message_data)
        else:
            message = GroupMessage.objects.create(**message_data)
            
        # Convert to dict
        message_dict = message.to_dict()
        
        # Update cache
        self.cache_manager.set_message(str(message.id), message_dict)
        self.cache_manager.add_message_to_conversation(conversation_id, message_dict)
        
        # Send WebSocket update
        self._send_message_update(conversation_id, 'message_created', message_dict)
        
        return message_dict
    
    def update_message(self, message_id: str, content: str, **kwargs) -> Dict:
        """Update a message with caching"""
        try:
            message = BaseMessage.objects.get(id=message_id)
            message.content = content
            message.updated_at = timezone.now()
            for key, value in kwargs.items():
                setattr(message, key, value)
            message.save()
            
            # Update cache
            message_dict = message.to_dict()
            self.cache_manager.set_message(message_id, message_dict)
            
            # Send WebSocket update
            self._send_message_update(str(message.conversation_id), 'message_updated', message_dict)
            
            return message_dict
            
        except ObjectDoesNotExist:
            return None
    
    def delete_message(self, message_id: str) -> bool:
        """Delete a message with cache cleanup"""
        try:
            message = BaseMessage.objects.get(id=message_id)
            conversation_id = str(message.conversation_id)
            
            # Delete from database
            message.delete()
            
            # Clean up cache
            self.cache_manager.delete_message(message_id)
            
            # Remove from conversation messages cache
            cached_messages = self.cache_manager.get_conversation_messages(conversation_id)
            if cached_messages:
                cached_messages = [msg for msg in cached_messages if str(msg.get('id')) != message_id]
                self.cache_manager.set_conversation_messages(conversation_id, cached_messages)
            
            # Send WebSocket update
            self._send_message_update(conversation_id, 'message_deleted', {'id': message_id})
            
            return True
            
        except ObjectDoesNotExist:
            return False
    
    def add_reaction(self, message_id: str, user_id: str, reaction: str) -> bool:
        """Add a reaction to a message"""
        self.cache_manager.add_message_reaction(message_id, user_id, reaction)
        # Update database
        try:
            message = BaseMessage.objects.get(id=message_id)
            message.add_reaction(user_id, reaction)
            return True
        except ObjectDoesNotExist:
            return False
    
    def remove_reaction(self, message_id: str, user_id: str, reaction: str) -> bool:
        """Remove a reaction from a message"""
        self.cache_manager.remove_message_reaction(message_id, user_id, reaction)
        # Update database
        try:
            message = BaseMessage.objects.get(id=message_id)
            message.remove_reaction(user_id, reaction)
            return True
        except ObjectDoesNotExist:
            return False
    
    def update_typing_status(self, conversation_id: str, user_id: str, 
                           is_typing: bool = True) -> None:
        """Update typing status for a user"""
        self.cache_manager.set_user_typing(conversation_id, user_id, is_typing)
        # Send WebSocket update
        self._send_typing_update(conversation_id, user_id, is_typing)
    
    def _send_message_update(self, conversation_id: str, event_type: str, 
                           message_data: Dict) -> None:
        """Send message update via WebSocket"""
        if not self.channel_layer:
            logger.warning("No channel layer available for WebSocket message delivery")
            return
            
        try:
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    "type": "chat.message",
                    "event_type": event_type,
                    "message": message_data
                }
            )
        except Exception as e:
            logger.error(f"Failed to send message update: {str(e)}")
            raise MessageDeliveryError(f"Error sending WebSocket message: {str(e)}")
    
    def _send_typing_update(self, conversation_id: str, user_id: str, 
                          is_typing: bool) -> None:
        """Send typing status update via WebSocket"""
        if not self.channel_layer:
            return
            
        try:
            group_name = f"conversation_{conversation_id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    "type": "typing.update",
                    "user_id": user_id,
                    "is_typing": is_typing
                }
            )
        except Exception as e:
            logger.error(f"Failed to send typing update: {str(e)}")
            raise MessageDeliveryError(f"Error sending WebSocket typing update: {str(e)}")