# datawarehouse/services/chatbot_messaging_service.py
from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime, timedelta
import time
import logging
from django.db.models import Count, Q
from django.utils import timezone
from chatbot.models import ChatbotConversation, ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class ChatbotMessagingDataSnapshot:
    """Structured data snapshot for chatbot messaging analytics"""

    # Basic metrics
    total_conversations: int
    total_messages: int
    active_conversations: int
    user_message_count: int
    bot_message_count: int

    # Conversation analytics
    conversation_statistics: Dict[str, Any]
    conversation_patterns: Dict[str, Any]

    # Message analytics
    message_statistics: Dict[str, Any]
    response_patterns: Dict[str, Any]

    # Engagement metrics
    engagement_metrics: Dict[str, Any]
    usage_patterns: Dict[str, Any]

    # Content analysis
    content_analysis: Dict[str, Any]
    topic_trends: Dict[str, Any]

    # Performance metrics
    performance_metrics: Dict[str, Any]
    timestamp: datetime


class ChatbotMessagingCollectionService:
    """Dedicated service for collecting and analyzing chatbot messaging data"""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    def collect_chatbot_data(
        self, user_id: int, days_back: int = 30
    ) -> ChatbotMessagingDataSnapshot:
        """
        Main entry point for collecting chatbot messaging data.

        Args:
            user_id: The user ID to collect data for
            days_back: Number of days to look back for data

        Returns:
            ChatbotMessagingDataSnapshot with comprehensive chatbot analytics
        """
        start_time = time.time()

        try:
            # Get raw data
            conversations_data = self._collect_raw_conversation_data(user_id, days_back)
            messages_data = self._collect_raw_message_data(user_id, days_back)

            # Calculate analytics
            conversation_stats = self._calculate_conversation_statistics(
                conversations_data
            )
            conversation_patterns = self._analyze_conversation_patterns(
                conversations_data, messages_data
            )

            message_stats = self._calculate_message_statistics(messages_data)
            response_patterns = self._analyze_response_patterns(messages_data)

            engagement_metrics = self._analyze_engagement_metrics(
                conversations_data, messages_data
            )
            usage_patterns = self._analyze_usage_patterns(
                conversations_data, messages_data
            )

            content_analysis = self._analyze_content_patterns(messages_data)
            topic_trends = self._analyze_topic_trends(messages_data)

            # Performance tracking
            processing_time = time.time() - start_time
            performance_metrics = {
                "processing_time_seconds": processing_time,
                "conversations_processed": len(conversations_data),
                "messages_processed": len(messages_data),
                "timestamp": timezone.now().isoformat(),
            }

            return ChatbotMessagingDataSnapshot(
                total_conversations=len(conversations_data),
                total_messages=len(messages_data),
                active_conversations=sum(
                    1 for conv in conversations_data if conv.get("is_active", False)
                ),
                user_message_count=sum(
                    1 for msg in messages_data if not msg.get("is_bot", False)
                ),
                bot_message_count=sum(
                    1 for msg in messages_data if msg.get("is_bot", False)
                ),
                conversation_statistics=conversation_stats,
                conversation_patterns=conversation_patterns,
                message_statistics=message_stats,
                response_patterns=response_patterns,
                engagement_metrics=engagement_metrics,
                usage_patterns=usage_patterns,
                content_analysis=content_analysis,
                topic_trends=topic_trends,
                performance_metrics=performance_metrics,
                timestamp=timezone.now(),
            )

        except Exception as e:
            logger.error(f"Error collecting chatbot data for user {user_id}: {str(e)}")
            # Return empty snapshot on error
            return self._create_empty_snapshot()

    def _collect_raw_conversation_data(
        self, user_id: int, days_back: int
    ) -> List[Dict]:
        """Collect raw conversation data from the database"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days_back)

            conversations = (
                ChatbotConversation.objects.filter(
                    user_id=user_id, created_at__gte=cutoff_date
                )
                .annotate(
                    message_count=Count("messages"),
                    user_message_count=Count(
                        "messages", filter=Q(messages__is_bot=False)
                    ),
                    bot_message_count=Count(
                        "messages", filter=Q(messages__is_bot=True)
                    ),
                )
                .values(
                    "id",
                    "title",
                    "created_at",
                    "last_activity",
                    "is_active",
                    "metadata",
                    "message_count",
                    "user_message_count",
                    "bot_message_count",
                )
            )

            return list(conversations)

        except Exception as e:
            logger.error(f"Error collecting conversation data: {str(e)}")
            return []

    def _collect_raw_message_data(self, user_id: int, days_back: int) -> List[Dict]:
        """Collect raw message data from the database"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days_back)

            messages = ChatMessage.objects.filter(
                conversation__user_id=user_id, timestamp__gte=cutoff_date
            ).values(
                "id",
                "conversation_id",
                "content",
                "is_bot",
                "timestamp",
                "message_type",
                "metadata",
                "sender_id",
                "parent_message_id",
            )

            return list(messages)

        except Exception as e:
            logger.error(f"Error collecting message data: {str(e)}")
            return []

    def _calculate_conversation_statistics(
        self, conversations_data: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate comprehensive conversation statistics"""
        if not conversations_data:
            return self._empty_conversation_stats()

        try:
            total_conversations = len(conversations_data)
            active_conversations = sum(
                1 for conv in conversations_data if conv.get("is_active", False)
            )

            # Message counts per conversation
            message_counts = [
                conv.get("message_count", 0) for conv in conversations_data
            ]
            avg_messages_per_conversation = (
                sum(message_counts) / len(message_counts) if message_counts else 0
            )

            # Duration analysis
            durations = []
            for conv in conversations_data:
                if conv.get("created_at") and conv.get("last_activity"):
                    created = conv["created_at"]
                    last_activity = conv["last_activity"]
                    if isinstance(created, str):
                        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if isinstance(last_activity, str):
                        last_activity = datetime.fromisoformat(
                            last_activity.replace("Z", "+00:00")
                        )

                    duration = (last_activity - created).total_seconds() / 3600  # hours
                    durations.append(duration)

            avg_conversation_duration = (
                sum(durations) / len(durations) if durations else 0
            )

            # User vs bot message ratios
            total_user_messages = sum(
                conv.get("user_message_count", 0) for conv in conversations_data
            )
            total_bot_messages = sum(
                conv.get("bot_message_count", 0) for conv in conversations_data
            )

            user_bot_ratio = (
                total_user_messages / total_bot_messages
                if total_bot_messages > 0
                else 0
            )

            return {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "inactive_conversations": total_conversations - active_conversations,
                "activity_rate": active_conversations / total_conversations
                if total_conversations > 0
                else 0,
                "average_messages_per_conversation": round(
                    avg_messages_per_conversation, 2
                ),
                "average_conversation_duration_hours": round(
                    avg_conversation_duration, 2
                ),
                "total_user_messages": total_user_messages,
                "total_bot_messages": total_bot_messages,
                "user_bot_message_ratio": round(user_bot_ratio, 2),
                "message_distribution": {
                    "min_messages": min(message_counts) if message_counts else 0,
                    "max_messages": max(message_counts) if message_counts else 0,
                    "median_messages": sorted(message_counts)[len(message_counts) // 2]
                    if message_counts
                    else 0,
                },
            }

        except Exception as e:
            logger.error(f"Error calculating conversation statistics: {str(e)}")
            return self._empty_conversation_stats()

    def _analyze_conversation_patterns(
        self, conversations_data: List[Dict], messages_data: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze patterns in conversation behavior"""
        try:
            if not conversations_data:
                return {
                    "creation_patterns": {},
                    "engagement_patterns": {},
                    "lifecycle_patterns": {},
                }

            # Creation time patterns
            creation_hours = {}
            creation_days = {}

            for conv in conversations_data:
                if conv.get("created_at"):
                    created = conv["created_at"]
                    if isinstance(created, str):
                        created = datetime.fromisoformat(created.replace("Z", "+00:00"))

                    hour = created.hour
                    day = created.strftime("%A")

                    creation_hours[hour] = creation_hours.get(hour, 0) + 1
                    creation_days[day] = creation_days.get(day, 0) + 1

            # Most active conversation periods
            most_active_hour = (
                max(creation_hours.items(), key=lambda x: x[1])
                if creation_hours
                else (0, 0)
            )
            most_active_day = (
                max(creation_days.items(), key=lambda x: x[1])
                if creation_days
                else ("Unknown", 0)
            )

            # Engagement patterns
            conv_message_map = {}
            for msg in messages_data:
                conv_id = msg.get("conversation_id")
                if conv_id not in conv_message_map:
                    conv_message_map[conv_id] = []
                conv_message_map[conv_id].append(msg)

            # Calculate response times and session lengths
            avg_session_lengths = []
            for conv_id, messages in conv_message_map.items():
                if len(messages) >= 2:
                    messages.sort(key=lambda x: x.get("timestamp", datetime.min))
                    first_msg = messages[0]["timestamp"]
                    last_msg = messages[-1]["timestamp"]

                    if isinstance(first_msg, str):
                        first_msg = datetime.fromisoformat(
                            first_msg.replace("Z", "+00:00")
                        )
                    if isinstance(last_msg, str):
                        last_msg = datetime.fromisoformat(
                            last_msg.replace("Z", "+00:00")
                        )

                    session_length = (
                        last_msg - first_msg
                    ).total_seconds() / 60  # minutes
                    avg_session_lengths.append(session_length)

            avg_session_length = (
                sum(avg_session_lengths) / len(avg_session_lengths)
                if avg_session_lengths
                else 0
            )

            return {
                "creation_patterns": {
                    "hourly_distribution": creation_hours,
                    "daily_distribution": creation_days,
                    "most_active_hour": most_active_hour[0],
                    "most_active_day": most_active_day[0],
                },
                "engagement_patterns": {
                    "average_session_length_minutes": round(avg_session_length, 2),
                    "conversations_with_multiple_messages": len(
                        [
                            conv
                            for conv in conversations_data
                            if conv.get("message_count", 0) > 1
                        ]
                    ),
                    "single_message_conversations": len(
                        [
                            conv
                            for conv in conversations_data
                            if conv.get("message_count", 0) == 1
                        ]
                    ),
                },
                "lifecycle_patterns": {
                    "conversations_started": len(conversations_data),
                    "active_conversations": sum(
                        1 for conv in conversations_data if conv.get("is_active", False)
                    ),
                    "retention_rate": sum(
                        1 for conv in conversations_data if conv.get("is_active", False)
                    )
                    / len(conversations_data)
                    if conversations_data
                    else 0,
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing conversation patterns: {str(e)}")
            return {
                "creation_patterns": {},
                "engagement_patterns": {},
                "lifecycle_patterns": {},
            }

    def _calculate_message_statistics(
        self, messages_data: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate comprehensive message statistics"""
        if not messages_data:
            return self._empty_message_stats()

        try:
            total_messages = len(messages_data)
            user_messages = [
                msg for msg in messages_data if not msg.get("is_bot", False)
            ]
            bot_messages = [msg for msg in messages_data if msg.get("is_bot", False)]

            # Content length analysis
            user_content_lengths = [
                len(msg.get("content", "")) for msg in user_messages
            ]
            bot_content_lengths = [len(msg.get("content", "")) for msg in bot_messages]

            avg_user_message_length = (
                sum(user_content_lengths) / len(user_content_lengths)
                if user_content_lengths
                else 0
            )
            avg_bot_message_length = (
                sum(bot_content_lengths) / len(bot_content_lengths)
                if bot_content_lengths
                else 0
            )

            # Message type analysis
            message_types = {}
            for msg in messages_data:
                msg_type = msg.get("message_type", "text")
                message_types[msg_type] = message_types.get(msg_type, 0) + 1

            # Response relationship analysis
            messages_with_parent = sum(
                1 for msg in messages_data if msg.get("parent_message_id")
            )

            return {
                "total_messages": total_messages,
                "user_messages": len(user_messages),
                "bot_messages": len(bot_messages),
                "user_message_percentage": (len(user_messages) / total_messages * 100)
                if total_messages > 0
                else 0,
                "bot_message_percentage": (len(bot_messages) / total_messages * 100)
                if total_messages > 0
                else 0,
                "average_user_message_length": round(avg_user_message_length, 2),
                "average_bot_message_length": round(avg_bot_message_length, 2),
                "message_types_distribution": message_types,
                "messages_with_parent": messages_with_parent,
                "standalone_messages": total_messages - messages_with_parent,
                "content_length_distribution": {
                    "user_messages": {
                        "min_length": min(user_content_lengths)
                        if user_content_lengths
                        else 0,
                        "max_length": max(user_content_lengths)
                        if user_content_lengths
                        else 0,
                        "median_length": sorted(user_content_lengths)[
                            len(user_content_lengths) // 2
                        ]
                        if user_content_lengths
                        else 0,
                    },
                    "bot_messages": {
                        "min_length": min(bot_content_lengths)
                        if bot_content_lengths
                        else 0,
                        "max_length": max(bot_content_lengths)
                        if bot_content_lengths
                        else 0,
                        "median_length": sorted(bot_content_lengths)[
                            len(bot_content_lengths) // 2
                        ]
                        if bot_content_lengths
                        else 0,
                    },
                },
            }

        except Exception as e:
            logger.error(f"Error calculating message statistics: {str(e)}")
            return self._empty_message_stats()

    def _analyze_response_patterns(self, messages_data: List[Dict]) -> Dict[str, Any]:
        """Analyze response patterns and timing"""
        try:
            if not messages_data:
                return {
                    "response_times": {},
                    "conversation_flow": {},
                    "interaction_patterns": {},
                }

            # Sort messages by conversation and timestamp
            conv_messages = {}
            for msg in messages_data:
                conv_id = msg.get("conversation_id")
                if conv_id not in conv_messages:
                    conv_messages[conv_id] = []
                conv_messages[conv_id].append(msg)

            # Analyze response times
            response_times = []
            user_initiated_conversations = 0
            bot_initiated_conversations = 0

            for conv_id, messages in conv_messages.items():
                messages.sort(key=lambda x: x.get("timestamp", datetime.min))

                if messages:
                    first_message = messages[0]
                    if first_message.get("is_bot"):
                        bot_initiated_conversations += 1
                    else:
                        user_initiated_conversations += 1

                # Calculate response times between user and bot messages
                for i in range(len(messages) - 1):
                    current_msg = messages[i]
                    next_msg = messages[i + 1]

                    # Check if this is a user -> bot or bot -> user transition
                    if current_msg.get("is_bot") != next_msg.get("is_bot"):
                        current_time = current_msg.get("timestamp")
                        next_time = next_msg.get("timestamp")

                        if current_time and next_time:
                            if isinstance(current_time, str):
                                current_time = datetime.fromisoformat(
                                    current_time.replace("Z", "+00:00")
                                )
                            if isinstance(next_time, str):
                                next_time = datetime.fromisoformat(
                                    next_time.replace("Z", "+00:00")
                                )

                            response_time = (next_time - current_time).total_seconds()
                            response_times.append(response_time)

            avg_response_time = (
                sum(response_times) / len(response_times) if response_times else 0
            )

            # Analyze conversation flow patterns
            message_sequences = []
            for conv_id, messages in conv_messages.items():
                if len(messages) >= 2:
                    sequence = []
                    for msg in messages:
                        sequence.append("bot" if msg.get("is_bot") else "user")
                    message_sequences.append(sequence)

            # Find common patterns
            pattern_counts = {}
            for sequence in message_sequences:
                for i in range(len(sequence) - 1):
                    pattern = f"{sequence[i]} -> {sequence[i+1]}"
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

            most_common_pattern = (
                max(pattern_counts.items(), key=lambda x: x[1])
                if pattern_counts
                else ("No patterns", 0)
            )

            return {
                "response_times": {
                    "average_response_time_seconds": round(avg_response_time, 2),
                    "total_responses_analyzed": len(response_times),
                    "fastest_response_seconds": min(response_times)
                    if response_times
                    else 0,
                    "slowest_response_seconds": max(response_times)
                    if response_times
                    else 0,
                },
                "conversation_flow": {
                    "user_initiated_conversations": user_initiated_conversations,
                    "bot_initiated_conversations": bot_initiated_conversations,
                    "common_patterns": pattern_counts,
                    "most_common_pattern": most_common_pattern[0],
                    "most_common_pattern_count": most_common_pattern[1],
                },
                "interaction_patterns": {
                    "total_conversations_analyzed": len(conv_messages),
                    "average_messages_per_conversation": sum(
                        len(msgs) for msgs in conv_messages.values()
                    )
                    / len(conv_messages)
                    if conv_messages
                    else 0,
                    "conversations_with_back_and_forth": len(
                        [msgs for msgs in conv_messages.values() if len(msgs) >= 4]
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing response patterns: {str(e)}")
            return {
                "response_times": {},
                "conversation_flow": {},
                "interaction_patterns": {},
            }

    def _analyze_engagement_metrics(
        self, conversations_data: List[Dict], messages_data: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze user engagement with the chatbot"""
        try:
            if not conversations_data:
                return {
                    "overall_engagement": {},
                    "session_metrics": {},
                    "retention_metrics": {},
                }

            # Overall engagement
            total_conversations = len(conversations_data)
            total_messages = len(messages_data)
            user_messages = [
                msg for msg in messages_data if not msg.get("is_bot", False)
            ]

            # Session analysis
            now = timezone.now()
            recent_conversations = [
                conv
                for conv in conversations_data
                if conv.get("last_activity")
                and (
                    now
                    - (
                        conv["last_activity"]
                        if isinstance(conv["last_activity"], datetime)
                        else datetime.fromisoformat(
                            conv["last_activity"].replace("Z", "+00:00")
                        )
                    )
                ).days
                <= 7
            ]

            # Active vs inactive
            active_conversations = [
                conv for conv in conversations_data if conv.get("is_active", False)
            ]

            # Engagement depth
            high_engagement_conversations = [
                conv
                for conv in conversations_data
                if conv.get("message_count", 0) >= 10
            ]

            return {
                "overall_engagement": {
                    "total_conversations": total_conversations,
                    "total_user_messages": len(user_messages),
                    "average_user_messages_per_conversation": len(user_messages)
                    / total_conversations
                    if total_conversations > 0
                    else 0,
                    "engagement_rate": len(user_messages) / total_messages
                    if total_messages > 0
                    else 0,
                },
                "session_metrics": {
                    "recent_conversations_7_days": len(recent_conversations),
                    "active_conversations": len(active_conversations),
                    "inactive_conversations": total_conversations
                    - len(active_conversations),
                    "activity_retention_rate": len(active_conversations)
                    / total_conversations
                    if total_conversations > 0
                    else 0,
                },
                "retention_metrics": {
                    "high_engagement_conversations": len(high_engagement_conversations),
                    "high_engagement_rate": len(high_engagement_conversations)
                    / total_conversations
                    if total_conversations > 0
                    else 0,
                    "average_conversation_depth": sum(
                        conv.get("message_count", 0) for conv in conversations_data
                    )
                    / total_conversations
                    if total_conversations > 0
                    else 0,
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing engagement metrics: {str(e)}")
            return {
                "overall_engagement": {},
                "session_metrics": {},
                "retention_metrics": {},
            }

    def _analyze_usage_patterns(
        self, conversations_data: List[Dict], messages_data: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze usage patterns over time"""
        try:
            if not messages_data:
                return {
                    "temporal_patterns": {},
                    "frequency_patterns": {},
                    "usage_trends": {},
                }

            # Temporal analysis
            hourly_usage = {}
            daily_usage = {}
            weekly_usage = {}

            for msg in messages_data:
                if msg.get("timestamp"):
                    timestamp = msg["timestamp"]
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )

                    hour = timestamp.hour
                    day = timestamp.strftime("%A")
                    week = timestamp.strftime("%Y-W%U")

                    hourly_usage[hour] = hourly_usage.get(hour, 0) + 1
                    daily_usage[day] = daily_usage.get(day, 0) + 1
                    weekly_usage[week] = weekly_usage.get(week, 0) + 1

            # Peak usage times
            peak_hour = (
                max(hourly_usage.items(), key=lambda x: x[1])
                if hourly_usage
                else (0, 0)
            )
            peak_day = (
                max(daily_usage.items(), key=lambda x: x[1])
                if daily_usage
                else ("Unknown", 0)
            )

            # Usage consistency
            weeks_with_usage = len(weekly_usage)
            avg_weekly_messages = (
                sum(weekly_usage.values()) / weeks_with_usage
                if weeks_with_usage > 0
                else 0
            )

            return {
                "temporal_patterns": {
                    "hourly_distribution": hourly_usage,
                    "daily_distribution": daily_usage,
                    "peak_usage_hour": peak_hour[0],
                    "peak_usage_day": peak_day[0],
                    "peak_hour_message_count": peak_hour[1],
                    "peak_day_message_count": peak_day[1],
                },
                "frequency_patterns": {
                    "weeks_with_usage": weeks_with_usage,
                    "average_weekly_messages": round(avg_weekly_messages, 2),
                    "most_active_week": max(weekly_usage.items(), key=lambda x: x[1])[0]
                    if weekly_usage
                    else "No data",
                    "weekly_usage_distribution": weekly_usage,
                },
                "usage_trends": {
                    "total_active_weeks": weeks_with_usage,
                    "consistency_score": min(
                        1.0, weeks_with_usage / 4
                    ),  # Normalized to 4 weeks
                    "usage_variance": self._calculate_variance(
                        list(weekly_usage.values())
                    )
                    if weekly_usage
                    else 0,
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing usage patterns: {str(e)}")
            return {
                "temporal_patterns": {},
                "frequency_patterns": {},
                "usage_trends": {},
            }

    def _analyze_content_patterns(self, messages_data: List[Dict]) -> Dict[str, Any]:
        """Analyze content patterns in messages"""
        try:
            if not messages_data:
                return {
                    "content_themes": {},
                    "message_characteristics": {},
                    "communication_style": {},
                }

            user_messages = [
                msg for msg in messages_data if not msg.get("is_bot", False)
            ]
            bot_messages = [msg for msg in messages_data if msg.get("is_bot", False)]

            # Content analysis keywords for mental health context
            mental_health_keywords = [
                "anxiety",
                "depression",
                "stress",
                "worry",
                "sad",
                "happy",
                "angry",
                "therapy",
                "counseling",
                "help",
                "support",
                "feel",
                "emotion",
                "mood",
                "mental",
                "health",
                "cope",
                "struggle",
                "better",
                "worse",
            ]

            # Analyze user message content
            keyword_mentions = {}
            question_count = 0
            exclamation_count = 0

            for msg in user_messages:
                content = msg.get("content", "").lower()

                # Count mental health keywords
                for keyword in mental_health_keywords:
                    if keyword in content:
                        keyword_mentions[keyword] = keyword_mentions.get(keyword, 0) + 1

                # Analyze punctuation patterns
                if "?" in content:
                    question_count += 1
                if "!" in content:
                    exclamation_count += 1

            # Most mentioned topics
            top_keywords = sorted(
                keyword_mentions.items(), key=lambda x: x[1], reverse=True
            )[:5]

            # Message characteristics
            avg_user_words = []
            avg_bot_words = []

            for msg in user_messages:
                content = msg.get("content", "")
                word_count = len(content.split())
                avg_user_words.append(word_count)

            for msg in bot_messages:
                content = msg.get("content", "")
                word_count = len(content.split())
                avg_bot_words.append(word_count)

            avg_user_word_count = (
                sum(avg_user_words) / len(avg_user_words) if avg_user_words else 0
            )
            avg_bot_word_count = (
                sum(avg_bot_words) / len(avg_bot_words) if avg_bot_words else 0
            )

            return {
                "content_themes": {
                    "mental_health_keyword_mentions": keyword_mentions,
                    "top_mentioned_topics": dict(top_keywords),
                    "total_unique_topics_mentioned": len(keyword_mentions),
                },
                "message_characteristics": {
                    "average_user_word_count": round(avg_user_word_count, 2),
                    "average_bot_word_count": round(avg_bot_word_count, 2),
                    "user_questions_asked": question_count,
                    "user_exclamations": exclamation_count,
                    "question_rate": question_count / len(user_messages)
                    if user_messages
                    else 0,
                },
                "communication_style": {
                    "user_message_length_category": self._categorize_message_length(
                        avg_user_word_count
                    ),
                    "engagement_level": self._calculate_engagement_level(
                        question_count, exclamation_count, len(user_messages)
                    ),
                    "conversation_formality": self._assess_formality(user_messages),
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing content patterns: {str(e)}")
            return {
                "content_themes": {},
                "message_characteristics": {},
                "communication_style": {},
            }

    def _analyze_topic_trends(self, messages_data: List[Dict]) -> Dict[str, Any]:
        """Analyze trending topics over time"""
        try:
            if not messages_data:
                return {
                    "trending_topics": {},
                    "topic_evolution": {},
                    "seasonal_patterns": {},
                }

            # Define topic categories for mental health
            topic_categories = {
                "emotional_state": [
                    "happy",
                    "sad",
                    "angry",
                    "frustrated",
                    "excited",
                    "calm",
                    "anxious",
                ],
                "coping_strategies": [
                    "meditation",
                    "exercise",
                    "breathing",
                    "therapy",
                    "medication",
                    "counseling",
                ],
                "life_events": [
                    "work",
                    "family",
                    "relationship",
                    "school",
                    "job",
                    "stress",
                    "change",
                ],
                "symptoms": [
                    "sleep",
                    "appetite",
                    "energy",
                    "concentration",
                    "mood",
                    "panic",
                    "worry",
                ],
                "support_seeking": [
                    "help",
                    "support",
                    "advice",
                    "guidance",
                    "talk",
                    "listen",
                    "understand",
                ],
            }

            # Analyze topics by time period
            monthly_topics = {}

            user_messages = [
                msg for msg in messages_data if not msg.get("is_bot", False)
            ]

            for msg in user_messages:
                content = msg.get("content", "").lower()
                timestamp = msg.get("timestamp")

                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )

                    month_key = timestamp.strftime("%Y-%m")

                    if month_key not in monthly_topics:
                        monthly_topics[month_key] = {}

                    # Check for topic categories
                    for category, keywords in topic_categories.items():
                        for keyword in keywords:
                            if keyword in content:
                                if category not in monthly_topics[month_key]:
                                    monthly_topics[month_key][category] = 0
                                monthly_topics[month_key][category] += 1

            # Find trending topics (increasing mentions over time)
            trending_analysis = {}
            if len(monthly_topics) >= 2:
                months = sorted(monthly_topics.keys())
                recent_month = months[-1]
                previous_month = months[-2] if len(months) >= 2 else months[-1]

                recent_topics = monthly_topics.get(recent_month, {})
                previous_topics = monthly_topics.get(previous_month, {})

                for topic in topic_categories.keys():
                    recent_count = recent_topics.get(topic, 0)
                    previous_count = previous_topics.get(topic, 0)

                    if previous_count > 0:
                        trend_change = (recent_count - previous_count) / previous_count
                    else:
                        trend_change = 1.0 if recent_count > 0 else 0.0

                    trending_analysis[topic] = {
                        "recent_mentions": recent_count,
                        "previous_mentions": previous_count,
                        "trend_change_percentage": round(trend_change * 100, 2),
                        "is_trending_up": trend_change > 0.2,
                        "is_trending_down": trend_change < -0.2,
                    }

            return {
                "trending_topics": trending_analysis,
                "topic_evolution": {
                    "monthly_topic_distribution": monthly_topics,
                    "most_discussed_category": max(
                        [
                            (
                                cat,
                                sum(
                                    monthly_topics.get(month, {}).get(cat, 0)
                                    for month in monthly_topics
                                ),
                            )
                            for cat in topic_categories.keys()
                        ],
                        key=lambda x: x[1],
                    )[0]
                    if monthly_topics
                    else "No data",
                    "topic_diversity_score": len(
                        set().union(
                            *(
                                monthly_topics.get(month, {}).keys()
                                for month in monthly_topics
                            )
                        )
                    ),
                },
                "seasonal_patterns": {
                    "active_months": len(monthly_topics),
                    "consistent_topics": [
                        topic
                        for topic in topic_categories.keys()
                        if sum(1 for month in monthly_topics.values() if topic in month)
                        >= len(monthly_topics) * 0.5
                    ]
                    if monthly_topics
                    else [],
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing topic trends: {str(e)}")
            return {
                "trending_topics": {},
                "topic_evolution": {},
                "seasonal_patterns": {},
            }

    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values"""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return round(variance, 2)

    def _categorize_message_length(self, avg_word_count: float) -> str:
        """Categorize message length"""
        if avg_word_count < 5:
            return "very_short"
        elif avg_word_count < 15:
            return "short"
        elif avg_word_count < 30:
            return "medium"
        elif avg_word_count < 50:
            return "long"
        else:
            return "very_long"

    def _calculate_engagement_level(
        self, questions: int, exclamations: int, total_messages: int
    ) -> str:
        """Calculate engagement level based on interaction patterns"""
        if total_messages == 0:
            return "no_data"

        interaction_score = (questions + exclamations) / total_messages

        if interaction_score >= 0.3:
            return "high"
        elif interaction_score >= 0.15:
            return "medium"
        else:
            return "low"

    def _assess_formality(self, user_messages: List[Dict]) -> str:
        """Assess formality level of communication"""
        if not user_messages:
            return "no_data"

        informal_indicators = ["lol", "omg", "btw", "thx", "u", "ur", "😊", "😢", "😟"]
        formal_indicators = [
            "please",
            "thank you",
            "appreciate",
            "kindly",
            "however",
            "furthermore",
        ]

        informal_count = 0
        formal_count = 0

        for msg in user_messages:
            content = msg.get("content", "").lower()

            for indicator in informal_indicators:
                if indicator in content:
                    informal_count += 1

            for indicator in formal_indicators:
                if indicator in content:
                    formal_count += 1

        if formal_count > informal_count:
            return "formal"
        elif informal_count > formal_count:
            return "informal"
        else:
            return "neutral"

    def _create_empty_snapshot(self) -> ChatbotMessagingDataSnapshot:
        """Create an empty snapshot for error cases"""
        return ChatbotMessagingDataSnapshot(
            total_conversations=0,
            total_messages=0,
            active_conversations=0,
            user_message_count=0,
            bot_message_count=0,
            conversation_statistics=self._empty_conversation_stats(),
            conversation_patterns={
                "creation_patterns": {},
                "engagement_patterns": {},
                "lifecycle_patterns": {},
            },
            message_statistics=self._empty_message_stats(),
            response_patterns={
                "response_times": {},
                "conversation_flow": {},
                "interaction_patterns": {},
            },
            engagement_metrics={
                "overall_engagement": {},
                "session_metrics": {},
                "retention_metrics": {},
            },
            usage_patterns={
                "temporal_patterns": {},
                "frequency_patterns": {},
                "usage_trends": {},
            },
            content_analysis={
                "content_themes": {},
                "message_characteristics": {},
                "communication_style": {},
            },
            topic_trends={
                "trending_topics": {},
                "topic_evolution": {},
                "seasonal_patterns": {},
            },
            performance_metrics={
                "processing_time_seconds": 0,
                "conversations_processed": 0,
                "messages_processed": 0,
                "timestamp": timezone.now().isoformat(),
            },
            timestamp=timezone.now(),
        )

    def _empty_conversation_stats(self) -> Dict[str, Any]:
        """Return empty conversation statistics"""
        return {
            "total_conversations": 0,
            "active_conversations": 0,
            "inactive_conversations": 0,
            "activity_rate": 0,
            "average_messages_per_conversation": 0,
            "average_conversation_duration_hours": 0,
            "total_user_messages": 0,
            "total_bot_messages": 0,
            "user_bot_message_ratio": 0,
            "message_distribution": {
                "min_messages": 0,
                "max_messages": 0,
                "median_messages": 0,
            },
        }

    def _empty_message_stats(self) -> Dict[str, Any]:
        """Return empty message statistics"""
        return {
            "total_messages": 0,
            "user_messages": 0,
            "bot_messages": 0,
            "user_message_percentage": 0,
            "bot_message_percentage": 0,
            "average_user_message_length": 0,
            "average_bot_message_length": 0,
            "message_types_distribution": {},
            "messages_with_parent": 0,
            "standalone_messages": 0,
            "content_length_distribution": {
                "user_messages": {"min_length": 0, "max_length": 0, "median_length": 0},
                "bot_messages": {"min_length": 0, "max_length": 0, "median_length": 0},
            },
        }
