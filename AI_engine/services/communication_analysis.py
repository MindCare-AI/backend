# AI_engine/services/communication_analysis.py
from typing import Dict, Any
import logging
from django.conf import settings
import requests
from django.utils import timezone
from datetime import timedelta
from ..models import CommunicationPatternAnalysis, AIInsight

logger = logging.getLogger(__name__)


class CommunicationAnalysisService:
    """Service to analyze user's communication patterns in the messaging app."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"
        self.analysis_period = 30  # Default analysis period in days

    def analyze_communication_patterns(self, user, days: int = None) -> Dict[str, Any]:
        """
        Analyze a user's communication patterns in the messaging app.

        This looks at message timing, content, and interactions to identify:
        - Therapeutic relationships
        - Communication style and effectiveness
        - Response patterns to different approaches
        - Topics that trigger emotional responses
        """
        try:
            analysis_period = days or self.analysis_period
            end_date = timezone.now()
            start_date = end_date - timedelta(days=analysis_period)

            # Import here to avoid circular imports
            from messaging.models.one_to_one import OneToOneMessage
            from messaging.models.group import GroupMessage
            from chatbot.models import ChatMessage

            # Get one-to-one messages
            sent_messages = OneToOneMessage.objects.filter(
                sender=user, timestamp__range=(start_date, end_date)
            ).select_related("conversation")

            received_messages = (
                OneToOneMessage.objects.filter(
                    conversation__participants=user,
                    timestamp__range=(start_date, end_date),
                )
                .exclude(sender=user)
                .select_related("sender", "conversation")
            )

            # Get group messages
            group_messages_sent = GroupMessage.objects.filter(
                sender=user, timestamp__range=(start_date, end_date)
            ).select_related("conversation")

            group_messages_received = (
                GroupMessage.objects.filter(
                    conversation__participants=user,
                    timestamp__range=(start_date, end_date),
                )
                .exclude(sender=user)
                .select_related("sender", "conversation")
            )

            # Get chatbot interactions
            chatbot_messages_sent = ChatMessage.objects.filter(
                sender=user, is_bot=False, timestamp__range=(start_date, end_date)
            ).select_related("conversation")

            chatbot_messages_received = ChatMessage.objects.filter(
                conversation__user=user,
                is_bot=True,
                timestamp__range=(start_date, end_date),
            ).select_related("conversation")

            # Prepare message data for analysis
            one_to_one_data = {
                "sent_messages": [
                    {
                        "conversation_id": msg.conversation.id,
                        "content": msg.content[:150]
                        if len(msg.content) > 150
                        else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "message_type": msg.message_type
                        if hasattr(msg, "message_type")
                        else "text",
                    }
                    for msg in sent_messages
                ],
                "received_messages": [
                    {
                        "conversation_id": msg.conversation.id,
                        "sender": msg.sender.username if msg.sender else "Unknown",
                        "sender_type": getattr(msg.sender, "user_type", "unknown"),
                        "content": msg.content[:150]
                        if len(msg.content) > 150
                        else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "message_type": msg.message_type
                        if hasattr(msg, "message_type")
                        else "text",
                    }
                    for msg in received_messages
                ],
            }

            group_data = {
                "sent_messages": [
                    {
                        "conversation_id": msg.conversation.id,
                        "conversation_name": msg.conversation.name
                        if hasattr(msg.conversation, "name")
                        else "Unknown",
                        "content": msg.content[:150]
                        if len(msg.content) > 150
                        else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in group_messages_sent
                ],
                "received_messages": [
                    {
                        "conversation_id": msg.conversation.id,
                        "conversation_name": msg.conversation.name
                        if hasattr(msg.conversation, "name")
                        else "Unknown",
                        "sender": msg.sender.username if msg.sender else "Unknown",
                        "content": msg.content[:150]
                        if len(msg.content) > 150
                        else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in group_messages_received
                ],
            }

            chatbot_data = {
                "user_messages": [
                    {
                        "content": msg.content[:150]
                        if len(msg.content) > 150
                        else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in chatbot_messages_sent
                ],
                "bot_responses": [
                    {
                        "content": msg.content[:150]
                        if len(msg.content) > 150
                        else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in chatbot_messages_received
                ],
            }

            # Additional metrics
            metrics = self._calculate_message_metrics(
                sent_messages,
                received_messages,
                group_messages_sent,
                group_messages_received,
                chatbot_messages_sent,
                chatbot_messages_received,
            )

            # Combine data for analysis
            analysis_data = {
                "one_to_one": one_to_one_data,
                "group": group_data,
                "chatbot": chatbot_data,
                "metrics": metrics,
            }

            # Use Ollama to generate insights
            analysis = self._analyze_with_ollama(analysis_data)

            # Store the analysis
            CommunicationPatternAnalysis.objects.create(
                user=user,
                analysis_date=timezone.now().date(),
                therapeutic_relationships=analysis.get("therapeutic_relationships", {}),
                conversation_metrics=analysis.get("conversation_metrics", {}),
                communication_style=analysis.get("communication_style", {}),
                response_patterns=analysis.get("response_patterns", {}),
                emotional_triggers=analysis.get("emotional_triggers", []),
                improvement_areas=analysis.get("improvement_areas", []),
            )

            # Generate insights if significant patterns are detected
            if analysis.get("needs_attention"):
                AIInsight.objects.create(
                    user=user,
                    insight_type="communication_pattern",
                    insight_data={
                        "pattern_type": analysis.get("attention_reason", "general"),
                        "description": analysis.get("attention_description", ""),
                        "suggestions": analysis.get("improvement_areas", []),
                    },
                    priority=analysis.get("priority_level", "medium"),
                )

            return analysis

        except Exception as e:
            logger.error(
                f"Error analyzing communication patterns: {str(e)}", exc_info=True
            )
            return self._create_default_analysis()

    def _calculate_message_metrics(
        self,
        sent_1to1,
        received_1to1,
        sent_group,
        received_group,
        sent_chatbot,
        received_chatbot,
    ) -> Dict[str, Any]:
        """Calculate metrics about user's messaging patterns"""

        # Messages by time of day
        def get_hour_distribution(messages):
            hours = {}
            for msg in messages:
                hour = msg.timestamp.hour
                hours[hour] = hours.get(hour, 0) + 1
            return hours

        # Message length distribution
        def get_length_metrics(messages):
            if not messages:
                return {"avg_length": 0, "min_length": 0, "max_length": 0}

            lengths = [len(msg.content) for msg in messages]
            return {
                "avg_length": sum(lengths) / len(lengths) if lengths else 0,
                "min_length": min(lengths) if lengths else 0,
                "max_length": max(lengths) if lengths else 0,
            }

        # Response time calculation
        def calculate_response_times(sent, received):
            # This is a simplified approach - would need more sophisticated
            # conversation tracking for accurate response times
            response_times = []

            conversation_last_received = {}
            for msg in sorted(received, key=lambda x: x.timestamp):
                conversation_last_received[msg.conversation_id] = msg.timestamp

            for msg in sent:
                if msg.conversation_id in conversation_last_received:
                    last_received = conversation_last_received[msg.conversation_id]
                    if msg.timestamp > last_received:
                        response_time = (msg.timestamp - last_received).total_seconds()
                        if response_time < 86400:  # Only count if less than 24 hours
                            response_times.append(response_time)

            if response_times:
                return {
                    "avg_response_time_seconds": sum(response_times)
                    / len(response_times),
                    "min_response_time_seconds": min(response_times),
                    "max_response_time_seconds": max(response_times),
                }
            return {"avg_response_time_seconds": 0}

        # Conversation activity
        conversations = {}
        for msg in list(sent_1to1) + list(received_1to1):
            if msg.conversation_id not in conversations:
                conversations[msg.conversation_id] = 0
            conversations[msg.conversation_id] += 1

        active_conversations = len(conversations)
        most_active_conversation = max(conversations.values()) if conversations else 0

        return {
            "total_messages_sent": len(sent_1to1) + len(sent_group) + len(sent_chatbot),
            "total_messages_received": len(received_1to1)
            + len(received_group)
            + len(received_chatbot),
            "one_to_one_sent": len(sent_1to1),
            "one_to_one_received": len(received_1to1),
            "group_sent": len(sent_group),
            "group_received": len(received_group),
            "chatbot_sent": len(sent_chatbot),
            "chatbot_received": len(received_chatbot),
            "hour_distribution_sent": get_hour_distribution(
                list(sent_1to1) + list(sent_group)
            ),
            "hour_distribution_received": get_hour_distribution(
                list(received_1to1) + list(received_group)
            ),
            "length_metrics_sent": get_length_metrics(
                list(sent_1to1) + list(sent_group)
            ),
            "length_metrics_received": get_length_metrics(
                list(received_1to1) + list(received_group)
            ),
            "active_conversations": active_conversations,
            "most_active_conversation_message_count": most_active_conversation,
        }

    def _analyze_with_ollama(self, data: Dict) -> Dict:
        """Analyze communication data using Ollama"""
        try:
            prompt = self._build_analysis_prompt(data)

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )

            if response.status_code == 200:
                result = response.json()
                return self._parse_analysis_response(result["response"])
            else:
                logger.error(
                    f"Ollama request failed with status {response.status_code}"
                )
                return self._create_default_analysis()

        except Exception as e:
            logger.error(f"Error in Ollama analysis: {str(e)}")
            return self._create_default_analysis()

    def _build_analysis_prompt(self, data: Dict) -> str:
        """Build prompt for Ollama communication analysis"""
        metrics = data.get("metrics", {})

        return f"""As a mental health AI specialist, analyze the following user's communication patterns in messaging and provide insights:

One-to-one messaging activity:
- Messages sent: {len(data['one_to_one']['sent_messages'])}
- Messages received: {len(data['one_to_one']['received_messages'])}
- Sample sent messages: {data['one_to_one']['sent_messages'][:5] if data['one_to_one']['sent_messages'] else []}
- Sample received messages: {data['one_to_one']['received_messages'][:5] if data['one_to_one']['received_messages'] else []}

Group messaging activity:
- Messages sent: {len(data['group']['sent_messages'])}
- Messages received: {len(data['group']['received_messages'])}

Chatbot interaction:
- Messages sent to bot: {len(data['chatbot']['user_messages'])}
- Messages received from bot: {len(data['chatbot']['bot_responses'])}

Messaging metrics:
- Total messages sent: {metrics.get('total_messages_sent', 0)}
- Total messages received: {metrics.get('total_messages_received', 0)}
- Average message length (sent): {metrics.get('length_metrics_sent', {}).get('avg_length', 0)}
- Active conversations: {metrics.get('active_conversations', 0)}
- Most active conversation message count: {metrics.get('most_active_conversation_message_count', 0)}
- Hour distribution of sent messages: {metrics.get('hour_distribution_sent', {})}

Analyze this data and provide insights in JSON format with these fields:
{{
    "therapeutic_relationships": {{<analysis of user's therapeutic communication relationships>}},
    "conversation_metrics": {{<key metrics and insights about conversation patterns>}},
    "communication_style": {{<user's communication style characteristics>}},
    "response_patterns": {{<patterns in how user responds to different approaches>}},
    "emotional_triggers": [<list of topics that trigger emotional responses>],
    "improvement_areas": [<list of areas where communication could be improved>],
    "needs_attention": <boolean indicating if there are concerning patterns>,
    "attention_reason": <if needs_attention is true, the reason>,
    "attention_description": <description of the pattern needing attention>,
    "priority_level": <"low", "medium", or "high">
}}"""

    def _parse_analysis_response(self, response: str) -> Dict:
        """Parse and validate Ollama's analysis response"""
        try:
            import json

            # Try to extract the JSON portion of the response
            if "```json" in response and "```" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
                analysis = json.loads(json_str)
            else:
                analysis = json.loads(response)

            required_fields = [
                "therapeutic_relationships",
                "conversation_metrics",
                "communication_style",
                "response_patterns",
                "emotional_triggers",
                "improvement_areas",
                "needs_attention",
            ]

            # Ensure all required fields exist
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = self._create_default_analysis()[field]

            return analysis

        except json.JSONDecodeError:
            logger.error("Failed to parse Ollama analysis response as JSON")
            return self._create_default_analysis()
        except Exception as e:
            logger.error(f"Error processing Ollama analysis: {str(e)}")
            return self._create_default_analysis()

    def _create_default_analysis(self) -> Dict:
        """Create a default analysis when AI analysis fails"""
        return {
            "therapeutic_relationships": {"quality": "unknown"},
            "conversation_metrics": {"message_frequency": "moderate"},
            "communication_style": {"primary_style": "neutral"},
            "response_patterns": {"avg_response_time": "unknown"},
            "emotional_triggers": [],
            "improvement_areas": ["establish regular communication"],
            "needs_attention": False,
        }

    def analyze_therapeutic_relationship(self, user, therapist_id) -> Dict[str, Any]:
        """
        Analyze the therapeutic relationship between a user and their therapist.

        This helps identify communication effectiveness and areas for improvement
        in the therapeutic relationship.
        """
        try:
            from django.contrib.auth import get_user_model
            from messaging.models.one_to_one import (
                OneToOneMessage,
                OneToOneConversation,
            )

            User = get_user_model()
            therapist = User.objects.get(id=therapist_id)

            # Get conversation between user and therapist
            conversation = (
                OneToOneConversation.objects.filter(participants=user)
                .filter(participants=therapist)
                .first()
            )

            if not conversation:
                return {"error": "No conversation found between user and therapist"}

            # Get messages from the conversation
            messages = (
                OneToOneMessage.objects.filter(conversation=conversation)
                .select_related("sender")
                .order_by("timestamp")
            )

            # Prepare data for analysis
            user_messages = [
                {
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in messages
                if msg.sender == user
            ]

            therapist_messages = [
                {
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in messages
                if msg.sender == therapist
            ]

            # Simple metrics
            total_messages = len(messages)
            user_message_count = len(user_messages)
            therapist_message_count = len(therapist_messages)

            conversation_days = (
                (messages.last().timestamp - messages.first().timestamp).days + 1
                if messages.count() > 1
                else 1
            )

            # Average messages per day
            messages_per_day = (
                total_messages / conversation_days if conversation_days else 0
            )

            # Message length statistics
            user_msg_lengths = [len(msg["content"]) for msg in user_messages]
            therapist_msg_lengths = [len(msg["content"]) for msg in therapist_messages]

            avg_user_msg_length = (
                sum(user_msg_lengths) / len(user_msg_lengths) if user_msg_lengths else 0
            )
            avg_therapist_msg_length = (
                sum(therapist_msg_lengths) / len(therapist_msg_lengths)
                if therapist_msg_lengths
                else 0
            )

            # Message timing analysis
            response_times = []
            for i, msg in enumerate(messages[1:], 1):
                if msg.sender != messages[i - 1].sender:  # If this is a response
                    response_time = (
                        msg.timestamp - messages[i - 1].timestamp
                    ).total_seconds()
                    if response_time < 86400:  # Only count if less than 24 hours
                        response_times.append(response_time)

            avg_response_time = (
                sum(response_times) / len(response_times) if response_times else 0
            )

            analysis = {
                "total_messages": total_messages,
                "user_message_count": user_message_count,
                "therapist_message_count": therapist_message_count,
                "messages_per_day": messages_per_day,
                "avg_user_msg_length": avg_user_msg_length,
                "avg_therapist_msg_length": avg_therapist_msg_length,
                "avg_response_time_seconds": avg_response_time,
                "conversation_duration_days": conversation_days,
                "communication_balance": user_message_count
                / (therapist_message_count or 1),
                "engagement_level": "high"
                if messages_per_day > 3
                else "medium"
                if messages_per_day > 1
                else "low",
            }

            return analysis

        except Exception as e:
            logger.error(
                f"Error analyzing therapeutic relationship: {str(e)}", exc_info=True
            )
            return {"error": str(e), "success": False}

    def analyze_response_effectiveness(self, user, days: int = 30) -> Dict[str, Any]:
        """
        Analyze which communication approaches are most effective with this user.

        This helps identify patterns in how the user responds to different
        communication styles.
        """
        try:
            from messaging.models.one_to_one import OneToOneMessage

            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Get messages received by user
            received_messages = (
                OneToOneMessage.objects.filter(
                    conversation__participants=user,
                    timestamp__range=(start_date, end_date),
                )
                .exclude(sender=user)
                .select_related("sender")
            )

            # Get user's responses
            user_messages = OneToOneMessage.objects.filter(
                sender=user, timestamp__range=(start_date, end_date)
            ).select_related("conversation")

            # This would require more sophisticated analysis in a real implementation
            # Here we'll just return some basic statistics

            # Count messages by sender
            senders = {}
            for msg in received_messages:
                sender = msg.sender.username
                if sender not in senders:
                    senders[sender] = {"count": 0, "responses": 0}
                senders[sender]["count"] += 1

            # Simple approach to count responses (messages sent shortly after receiving)
            for msg in user_messages:
                # Get the most recent received message before this one
                previous = (
                    received_messages.filter(
                        conversation=msg.conversation, timestamp__lt=msg.timestamp
                    )
                    .order_by("-timestamp")
                    .first()
                )

                if (
                    previous
                    and (msg.timestamp - previous.timestamp).total_seconds() < 3600
                ):  # Within an hour
                    sender = previous.sender.username
                    if sender in senders:
                        senders[sender]["responses"] += 1

            # Calculate response rates
            for sender, data in senders.items():
                data["response_rate"] = (
                    data["responses"] / data["count"] if data["count"] > 0 else 0
                )

            return {
                "senders": senders,
                "most_responded_to": max(
                    senders.items(), key=lambda x: x[1]["response_rate"]
                )[0]
                if senders
                else None,
            }

        except Exception as e:
            logger.error(
                f"Error analyzing response effectiveness: {str(e)}", exc_info=True
            )
            return {"error": str(e), "success": False}


# Create singleton instance
communication_analysis_service = CommunicationAnalysisService()
