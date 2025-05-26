# AI_engine/services/conversation_summary.py
from typing import Dict, List, Any
import logging
from django.conf import settings
import requests
from ..models import ConversationSummary

logger = logging.getLogger(__name__)


class ConversationSummaryService:
    """Service to summarize older conversation parts for chatbot context management."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"
        self.max_messages_per_summary = 20

    def generate_conversation_summary(
        self, conversation_id: str, user
    ) -> Dict[str, Any]:
        """
        Generate a summary of older messages in a conversation.

        This helps maintain context while limiting the number of messages
        sent to the chatbot model.
        """
        try:
            # Import here to avoid circular imports
            from chatbot.models import ChatMessage, ChatbotConversation
            from messaging.models.one_to_one import (
                OneToOneMessage,
                OneToOneConversation,
            )

            # Determine conversation type and get messages
            try:
                ChatbotConversation.objects.get(id=conversation_id)
                messages = ChatMessage.objects.filter(
                    conversation_id=conversation_id
                ).order_by("timestamp")
            except ChatbotConversation.DoesNotExist:
                try:
                    OneToOneConversation.objects.get(id=conversation_id)
                    messages = OneToOneMessage.objects.filter(
                        conversation_id=conversation_id
                    ).order_by("timestamp")
                except OneToOneConversation.DoesNotExist:
                    return {"error": "Conversation not found"}

            # Count total messages
            total_messages = messages.count()

            # If there are few messages, no need for summarization
            if total_messages <= 6:
                return {
                    "needs_summary": False,
                    "total_messages": total_messages,
                    "message": "Not enough messages to summarize",
                }

            # Get the most recent summary for this conversation
            latest_summary = (
                ConversationSummary.objects.filter(
                    conversation_id=conversation_id, user=user
                )
                .order_by("-created_at")
                .first()
            )

            if latest_summary:
                # If we have a summary, only look at messages after the last one in that summary
                end_message_id = latest_summary.end_message_id
                messages_to_summarize = messages.filter(id__gt=end_message_id).order_by(
                    "timestamp"
                )[:-6]  # Exclude the 6 latest messages
            else:
                # If no summary yet, summarize all except the latest 6
                messages_to_summarize = messages.order_by("timestamp")[:-6]

            # If there aren't enough new messages to summarize, skip
            if messages_to_summarize.count() < 5:
                return {
                    "needs_summary": False,
                    "total_messages": total_messages,
                    "summarized_messages": 0,
                    "message": "Not enough new messages to summarize",
                }

            # Get the messages to summarize
            message_data = []
            for msg in messages_to_summarize:
                sender_type = "bot" if hasattr(msg, "is_bot") and msg.is_bot else "user"
                if not hasattr(msg, "is_bot"):
                    if msg.sender == user:
                        sender_type = "user"
                    else:
                        sender_type = "other"

                message_data.append(
                    {
                        "id": str(msg.id),
                        "content": msg.content,
                        "sender_type": sender_type,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                )

            # Use Ollama to generate a summary
            summary = self._generate_summary_with_ollama(message_data)

            # Save the summary
            start_message = messages_to_summarize.first()
            end_message = messages_to_summarize.last()

            if start_message and end_message:
                conversation_summary = ConversationSummary.objects.create(
                    conversation_id=conversation_id,
                    user=user,
                    start_message_id=start_message.id,
                    end_message_id=end_message.id,
                    message_count=messages_to_summarize.count(),
                    summary_text=summary.get("summary", ""),
                    key_points=summary.get("key_points", []),
                    emotional_context=summary.get("emotional_context", {}),
                )

                return {
                    "needs_summary": True,
                    "summary_id": conversation_summary.id,
                    "summary": summary.get("summary", ""),
                    "key_points": summary.get("key_points", []),
                    "emotional_context": summary.get("emotional_context", {}),
                    "summarized_messages": messages_to_summarize.count(),
                    "total_messages": total_messages,
                }
            else:
                return {
                    "needs_summary": False,
                    "total_messages": total_messages,
                    "message": "No messages to summarize",
                }

        except Exception as e:
            logger.error(
                f"Error generating conversation summary: {str(e)}", exc_info=True
            )
            return {"error": str(e), "success": False}

    def _generate_summary_with_ollama(self, messages: List[Dict]) -> Dict[str, Any]:
        """Generate a summary of conversation messages using Ollama"""
        try:
            prompt = self._build_summary_prompt(messages)

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )

            if response.status_code == 200:
                result = response.json()
                return self._parse_summary_response(result["response"])
            else:
                logger.error(
                    f"Ollama request failed with status {response.status_code}"
                )
                return self._create_default_summary()

        except Exception as e:
            logger.error(f"Error in Ollama summary generation: {str(e)}")
            return self._create_default_summary()

    def _build_summary_prompt(self, messages: List[Dict]) -> str:
        """Build prompt for Ollama summary generation"""
        messages_text = "\n\n".join(
            [
                f"[{msg.get('sender_type', 'user')}]: {msg.get('content', '')}"
                for msg in messages
            ]
        )

        return f"""As an AI assistant, summarize the following conversation while preserving key information:

{messages_text}

Please provide a comprehensive summary in JSON format with these fields:
{{
    "summary": <a concise summary of the conversation in 3-5 sentences>,
    "key_points": [<list of the key points or topics discussed>],
    "emotional_context": {{<analysis of the emotional context of the conversation>}}
}}"""

    def _parse_summary_response(self, response: str) -> Dict:
        """Parse and validate Ollama's summary response"""
        try:
            import json

            # Try to extract the JSON portion of the response
            if "```json" in response and "```" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
                summary = json.loads(json_str)
            else:
                summary = json.loads(response)

            required_fields = ["summary", "key_points", "emotional_context"]

            # Ensure all required fields exist
            for field in required_fields:
                if field not in summary:
                    summary[field] = self._create_default_summary()[field]

            return summary

        except json.JSONDecodeError:
            logger.error("Failed to parse Ollama summary response as JSON")
            return self._create_default_summary()
        except Exception as e:
            logger.error(f"Error processing Ollama summary: {str(e)}")
            return self._create_default_summary()

    def _create_default_summary(self) -> Dict:
        """Create a default summary when AI analysis fails"""
        return {
            "summary": "This is a conversation about various topics.",
            "key_points": ["General discussion"],
            "emotional_context": {"overall_tone": "neutral"},
        }

    def get_conversation_context(self, conversation_id: str, user) -> Dict[str, Any]:
        """
        Get the context for a conversation to enhance chatbot understanding.

        This returns:
        1. The most recent summary of older messages
        2. The 6 most recent messages
        """
        try:
            # Import here to avoid circular imports
            from chatbot.models import ChatMessage

            # Validate conversation_id - it should be a valid integer for ChatMessage
            try:
                conversation_id_int = int(conversation_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid conversation ID format: {conversation_id}")
                return {
                    "error": "Invalid conversation ID format",
                    "success": False,
                    "recent_messages": [],
                    "has_summary": False,
                }

            # Get the most recent summary
            latest_summary = (
                ConversationSummary.objects.filter(
                    conversation_id=conversation_id, user=user
                )
                .order_by("-created_at")
                .first()
            )

            # Get the 6 most recent messages
            recent_messages = ChatMessage.objects.filter(
                conversation_id=conversation_id_int
            ).order_by("-timestamp")[:6]

            # Format the recent messages
            messages = []
            for msg in reversed(recent_messages):
                sender_type = "bot" if msg.is_bot else "user"
                messages.append(
                    {
                        "id": str(msg.id),
                        "content": msg.content,
                        "sender_type": sender_type,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                )

            result = {"recent_messages": messages}

            # Add summary if available
            if latest_summary:
                result["has_summary"] = True
                result["summary"] = latest_summary.summary_text
                result["key_points"] = latest_summary.key_points
                result["emotional_context"] = latest_summary.emotional_context
                result["summarized_message_count"] = latest_summary.message_count
            else:
                result["has_summary"] = False

            return result

        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}", exc_info=True)
            return {
                "error": str(e),
                "success": False,
                "recent_messages": [],
                "has_summary": False,
            }

    def get_or_create_summary(
        self, conversation_id: str, user, messages: list
    ) -> Dict[str, Any]:
        """Get existing summary or create a new one if needed"""
        try:
            # Get the most recent summary
            latest_summary = (
                ConversationSummary.objects.filter(
                    conversation_id=conversation_id, user=user
                )
                .order_by("-created_at")
                .first()
            )

            if latest_summary:
                return {
                    "text": latest_summary.summary_text,
                    "key_points": latest_summary.key_points,
                    "emotional_context": latest_summary.emotional_context,
                }

            # If no existing summary, create one for the older messages
            if len(messages) <= 6:  # Don't summarize if there are few messages
                return {
                    "text": "Beginning of conversation",
                    "key_points": ["Initial messages"],
                    "emotional_context": {"overall_tone": "neutral"},
                }

            # Get all except the 6 most recent messages for summarization
            messages_to_summarize = messages[:-6]

            # Use Ollama to generate a summary
            summary = self._generate_summary_with_ollama(messages_to_summarize)

            # Create and save the summary
            start_message = messages_to_summarize[0]
            end_message = messages_to_summarize[-1]

            conversation_summary = ConversationSummary.objects.create(
                conversation_id=conversation_id,
                user=user,
                start_message_id=start_message.get("id"),
                end_message_id=end_message.get("id"),
                message_count=len(messages_to_summarize),
                summary_text=summary.get("summary", ""),
                key_points=summary.get("key_points", []),
                emotional_context=summary.get("emotional_context", {}),
            )

            return {
                "text": conversation_summary.summary_text,
                "key_points": conversation_summary.key_points,
                "emotional_context": conversation_summary.emotional_context,
            }

        except Exception as e:
            logger.error(f"Error getting/creating conversation summary: {str(e)}")
            return {
                "text": "Unable to generate summary",
                "key_points": ["Error generating summary"],
                "emotional_context": {"overall_tone": "neutral"},
            }

    def update_summary(
        self, conversation_id: str, user, conversation_history: list
    ) -> None:
        """
        Update the conversation summary for the given conversation.
        This method re-generates the summary for older messages.
        """
        try:
            # Reuse the get_or_create_summary method to update the summary
            # Removed unused variable 'summary_data'
            self.get_or_create_summary(conversation_id, user, conversation_history)
            logger.info(
                f"Updated conversation summary for conversation {conversation_id}"
            )
        except Exception as e:
            logger.error(f"Error updating conversation summary: {str(e)}")


# Create singleton instance
conversation_summary_service = ConversationSummaryService()
