# datawarehouse/services/messaging_collection_service.py

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from django.db.models import Q
from django.utils import timezone
from collections import defaultdict, Counter

# Import Django models
from messaging.models.one_to_one import OneToOneMessage, OneToOneConversation
from messaging.models.group import GroupMessage, GroupConversation
from chatbot.models import ChatMessage, ChatbotConversation

logger = logging.getLogger(__name__)


@dataclass
class ConversationMetrics:
    """Metrics for a single conversation"""

    message_count: int = 0
    avg_response_time: float = 0.0
    sentiment_score: float = 0.0
    therapeutic_keywords: List[str] = field(default_factory=list)
    engagement_score: float = 0.0
    last_activity: Optional[datetime] = None
    participant_count: int = 0


@dataclass
class MessagingAnalysisResult:
    """Comprehensive messaging analysis result"""

    # Basic metrics
    total_messages: int = 0
    total_conversations: int = 0
    avg_messages_per_conversation: float = 0.0

    # Communication patterns
    communication_frequency: Dict[str, int] = field(default_factory=dict)
    peak_activity_hours: List[int] = field(default_factory=list)
    response_time_patterns: Dict[str, float] = field(default_factory=dict)

    # Conversation analysis
    conversation_metrics: Dict[str, ConversationMetrics] = field(default_factory=dict)
    active_conversations: List[str] = field(default_factory=list)

    # Sentiment and therapeutic analysis
    overall_sentiment: float = 0.0
    emotional_trends: Dict[str, List[float]] = field(default_factory=dict)
    therapeutic_engagement: float = 0.0
    crisis_indicators: List[Dict[str, Any]] = field(default_factory=list)

    # Chatbot specific
    chatbot_interactions: int = 0
    chatbot_effectiveness: float = 0.0
    common_queries: List[Tuple[str, int]] = field(default_factory=list)

    # Support network analysis
    support_network_strength: float = 0.0
    social_connections: Dict[str, int] = field(default_factory=dict)

    # Insights and recommendations
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Metadata
    collection_timestamp: datetime = field(default_factory=timezone.now)
    analysis_period: str = ""


class MessagingCollectionService:
    """Service for collecting and analyzing messaging data"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Therapeutic keywords for analysis
        self.therapeutic_keywords = {
            "anxiety": ["anxious", "worried", "nervous", "panic", "fear"],
            "depression": ["sad", "depressed", "hopeless", "empty", "worthless"],
            "stress": ["stressed", "overwhelmed", "pressure", "tension"],
            "support": ["help", "support", "care", "understand", "listen"],
            "coping": ["cope", "manage", "handle", "deal with", "overcome"],
            "therapy": ["therapy", "counseling", "session", "therapist", "treatment"],
            "medication": [
                "medication",
                "pills",
                "prescription",
                "dosage",
                "side effects",
            ],
            "crisis": [
                "suicide",
                "kill myself",
                "end it all",
                "hurt myself",
                "can't go on",
            ],
        }

        # Crisis keywords that need immediate attention
        self.crisis_keywords = [
            "suicide",
            "kill myself",
            "end it all",
            "hurt myself",
            "can't go on",
            "want to die",
            "no point living",
        ]

    def collect_messaging_data(
        self, patient_id: int, days: int = 30
    ) -> MessagingAnalysisResult:
        """
        Collect and analyze messaging data for a patient

        Args:
            patient_id: ID of the patient
            days: Number of days to analyze (default: 30)

        Returns:
            MessagingAnalysisResult with comprehensive analysis
        """
        try:
            self.logger.info(
                f"Starting messaging data collection for patient {patient_id}"
            )

            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Initialize result
            result = MessagingAnalysisResult(
                analysis_period=f"{start_date.date()} to {end_date.date()}"
            )

            # Collect one-to-one messages
            self._analyze_one_to_one_messages(patient_id, start_date, end_date, result)

            # Collect group messages
            self._analyze_group_messages(patient_id, start_date, end_date, result)

            # Collect chatbot interactions
            self._analyze_chatbot_messages(patient_id, start_date, end_date, result)

            # Perform advanced analysis
            self._analyze_communication_patterns(result)
            self._analyze_sentiment_trends(result)
            self._detect_crisis_indicators(result)
            self._analyze_support_network(result)
            self._generate_insights(result)

            self.logger.info(
                f"Messaging data collection completed for patient {patient_id}"
            )
            return result

        except Exception as e:
            self.logger.error(
                f"Error collecting messaging data for patient {patient_id}: {str(e)}"
            )
            raise

    def _analyze_one_to_one_messages(
        self,
        patient_id: int,
        start_date: datetime,
        end_date: datetime,
        result: MessagingAnalysisResult,
    ):
        """Analyze one-to-one conversations"""
        try:
            # Get conversations where patient is participant
            conversations = OneToOneConversation.objects.filter(
                Q(participant1_id=patient_id) | Q(participant2_id=patient_id)
            )

            for conversation in conversations:
                messages = OneToOneMessage.objects.filter(
                    conversation=conversation, timestamp__range=[start_date, end_date]
                ).order_by("timestamp")

                if messages.exists():
                    conv_id = f"one_to_one_{conversation.id}"
                    metrics = ConversationMetrics()

                    metrics.message_count = messages.count()
                    metrics.participant_count = 2
                    metrics.last_activity = messages.last().timestamp

                    # Calculate response times and sentiment
                    patient_messages = messages.filter(sender_id=patient_id)
                    other_messages = messages.exclude(sender_id=patient_id)

                    # Calculate average response time
                    response_times = []
                    for i, msg in enumerate(patient_messages):
                        prev_other_msg = other_messages.filter(
                            timestamp__lt=msg.timestamp
                        ).last()
                        if prev_other_msg:
                            response_time = (
                                msg.timestamp - prev_other_msg.timestamp
                            ).total_seconds() / 3600
                            response_times.append(response_time)

                    if response_times:
                        metrics.avg_response_time = sum(response_times) / len(
                            response_times
                        )

                    # Analyze message content for therapeutic keywords
                    all_content = " ".join(
                        [msg.content for msg in messages if msg.content]
                    )
                    metrics.therapeutic_keywords = self._extract_therapeutic_keywords(
                        all_content
                    )
                    metrics.sentiment_score = self._calculate_sentiment_score(
                        all_content
                    )
                    metrics.engagement_score = self._calculate_engagement_score(metrics)

                    result.conversation_metrics[conv_id] = metrics
                    result.total_messages += metrics.message_count

                    if (
                        metrics.last_activity
                        and metrics.last_activity > timezone.now() - timedelta(days=7)
                    ):
                        result.active_conversations.append(conv_id)

            result.total_conversations += conversations.count()

        except Exception as e:
            self.logger.error(f"Error analyzing one-to-one messages: {str(e)}")

    def _analyze_group_messages(
        self,
        patient_id: int,
        start_date: datetime,
        end_date: datetime,
        result: MessagingAnalysisResult,
    ):
        """Analyze group conversations"""
        try:
            # Get group conversations where patient is a member
            conversations = GroupConversation.objects.filter(members__id=patient_id)

            for conversation in conversations:
                messages = GroupMessage.objects.filter(
                    conversation=conversation, timestamp__range=[start_date, end_date]
                ).order_by("timestamp")

                if messages.exists():
                    conv_id = f"group_{conversation.id}"
                    metrics = ConversationMetrics()

                    metrics.message_count = messages.count()
                    metrics.participant_count = conversation.members.count()
                    metrics.last_activity = messages.last().timestamp

                    # Analyze patient's participation
                    patient_messages = messages.filter(sender_id=patient_id)

                    # Calculate engagement based on participation ratio
                    if metrics.message_count > 0:
                        participation_ratio = (
                            patient_messages.count() / metrics.message_count
                        )
                        metrics.engagement_score = min(
                            participation_ratio * 5, 5.0
                        )  # Scale to 5

                    # Analyze content
                    all_content = " ".join(
                        [msg.content for msg in messages if msg.content]
                    )
                    metrics.therapeutic_keywords = self._extract_therapeutic_keywords(
                        all_content
                    )
                    metrics.sentiment_score = self._calculate_sentiment_score(
                        all_content
                    )

                    result.conversation_metrics[conv_id] = metrics
                    result.total_messages += metrics.message_count

                    if (
                        metrics.last_activity
                        and metrics.last_activity > timezone.now() - timedelta(days=7)
                    ):
                        result.active_conversations.append(conv_id)

            result.total_conversations += conversations.count()

        except Exception as e:
            self.logger.error(f"Error analyzing group messages: {str(e)}")

    def _analyze_chatbot_messages(
        self,
        patient_id: int,
        start_date: datetime,
        end_date: datetime,
        result: MessagingAnalysisResult,
    ):
        """Analyze chatbot interactions"""
        try:
            conversations = ChatbotConversation.objects.filter(user_id=patient_id)

            query_counter = Counter()
            total_interactions = 0
            effectiveness_scores = []

            for conversation in conversations:
                messages = ChatMessage.objects.filter(
                    conversation=conversation, timestamp__range=[start_date, end_date]
                ).order_by("timestamp")

                if messages.exists():
                    conv_id = f"chatbot_{conversation.id}"
                    metrics = ConversationMetrics()

                    user_messages = messages.filter(is_from_user=True)
                    bot_messages = messages.filter(is_from_user=False)

                    metrics.message_count = messages.count()
                    metrics.participant_count = 2  # User + bot
                    metrics.last_activity = messages.last().timestamp

                    # Analyze user queries
                    for msg in user_messages:
                        if msg.content:
                            # Simple query categorization
                            content_lower = msg.content.lower()
                            if any(
                                word in content_lower for word in ["help", "support"]
                            ):
                                query_counter["help_requests"] += 1
                            elif any(
                                word in content_lower for word in ["mood", "feeling"]
                            ):
                                query_counter["mood_inquiries"] += 1
                            elif any(
                                word in content_lower
                                for word in ["medication", "prescription"]
                            ):
                                query_counter["medication_questions"] += 1
                            else:
                                query_counter["general_questions"] += 1

                    # Calculate effectiveness based on conversation length and sentiment
                    if user_messages.count() > 0 and bot_messages.count() > 0:
                        # Longer conversations might indicate engagement
                        length_score = min(messages.count() / 10, 1.0)

                        # Analyze if user expresses satisfaction
                        all_content = " ".join(
                            [msg.content for msg in user_messages if msg.content]
                        )
                        satisfaction_keywords = [
                            "thank",
                            "helpful",
                            "better",
                            "good",
                            "useful",
                        ]
                        satisfaction_score = sum(
                            1
                            for word in satisfaction_keywords
                            if word in all_content.lower()
                        ) / len(satisfaction_keywords)

                        effectiveness = (length_score + satisfaction_score) / 2
                        effectiveness_scores.append(effectiveness)
                        metrics.engagement_score = effectiveness * 5  # Scale to 5

                    # Analyze content for therapeutic value
                    all_content = " ".join(
                        [msg.content for msg in messages if msg.content]
                    )
                    metrics.therapeutic_keywords = self._extract_therapeutic_keywords(
                        all_content
                    )
                    metrics.sentiment_score = self._calculate_sentiment_score(
                        all_content
                    )

                    result.conversation_metrics[conv_id] = metrics
                    result.total_messages += metrics.message_count
                    total_interactions += 1

                    if (
                        metrics.last_activity
                        and metrics.last_activity > timezone.now() - timedelta(days=7)
                    ):
                        result.active_conversations.append(conv_id)

            result.chatbot_interactions = total_interactions
            result.common_queries = query_counter.most_common(5)

            if effectiveness_scores:
                result.chatbot_effectiveness = sum(effectiveness_scores) / len(
                    effectiveness_scores
                )

        except Exception as e:
            self.logger.error(f"Error analyzing chatbot messages: {str(e)}")

    def _analyze_communication_patterns(self, result: MessagingAnalysisResult):
        """Analyze communication patterns and timing"""
        try:
            if result.total_conversations > 0:
                result.avg_messages_per_conversation = (
                    result.total_messages / result.total_conversations
                )

            # Analyze activity patterns by hour
            hour_activity = defaultdict(int)
            day_activity = defaultdict(int)

            for metrics in result.conversation_metrics.values():
                if metrics.last_activity:
                    hour = metrics.last_activity.hour
                    day = metrics.last_activity.strftime("%A")
                    hour_activity[hour] += metrics.message_count
                    day_activity[day] += metrics.message_count

            # Find peak activity hours (top 3)
            if hour_activity:
                sorted_hours = sorted(
                    hour_activity.items(), key=lambda x: x[1], reverse=True
                )
                result.peak_activity_hours = [hour for hour, _ in sorted_hours[:3]]

            # Communication frequency by day
            result.communication_frequency = dict(day_activity)

            # Response time patterns
            response_times = []
            for metrics in result.conversation_metrics.values():
                if metrics.avg_response_time > 0:
                    response_times.append(metrics.avg_response_time)

            if response_times:
                result.response_time_patterns = {
                    "average": sum(response_times) / len(response_times),
                    "min": min(response_times),
                    "max": max(response_times),
                }

        except Exception as e:
            self.logger.error(f"Error analyzing communication patterns: {str(e)}")

    def _analyze_sentiment_trends(self, result: MessagingAnalysisResult):
        """Analyze sentiment trends across conversations"""
        try:
            sentiments = []
            daily_sentiments = defaultdict(list)

            for conv_id, metrics in result.conversation_metrics.items():
                if metrics.sentiment_score != 0:
                    sentiments.append(metrics.sentiment_score)

                    if metrics.last_activity:
                        day = metrics.last_activity.date().isoformat()
                        daily_sentiments[day].append(metrics.sentiment_score)

            if sentiments:
                result.overall_sentiment = sum(sentiments) / len(sentiments)

            # Calculate daily sentiment averages
            for day, day_sentiments in daily_sentiments.items():
                if day_sentiments:
                    avg_sentiment = sum(day_sentiments) / len(day_sentiments)
                    result.emotional_trends[day] = [avg_sentiment]

        except Exception as e:
            self.logger.error(f"Error analyzing sentiment trends: {str(e)}")

    def _detect_crisis_indicators(self, result: MessagingAnalysisResult):
        """Detect potential crisis indicators in messages"""
        try:
            for conv_id, metrics in result.conversation_metrics.items():
                # Check for crisis keywords in therapeutic keywords
                crisis_found = any(
                    keyword in " ".join(metrics.therapeutic_keywords).lower()
                    for keyword in self.crisis_keywords
                )

                if crisis_found or metrics.sentiment_score < -0.7:
                    indicator = {
                        "conversation_id": conv_id,
                        "type": "crisis_language"
                        if crisis_found
                        else "severe_negative_sentiment",
                        "severity": "high" if crisis_found else "medium",
                        "timestamp": metrics.last_activity.isoformat()
                        if metrics.last_activity
                        else None,
                        "sentiment_score": metrics.sentiment_score,
                    }
                    result.crisis_indicators.append(indicator)

        except Exception as e:
            self.logger.error(f"Error detecting crisis indicators: {str(e)}")

    def _analyze_support_network(self, result: MessagingAnalysisResult):
        """Analyze the strength of the patient's support network"""
        try:
            active_connections = 0
            total_engagement = 0
            connection_types = defaultdict(int)

            for conv_id, metrics in result.conversation_metrics.values():
                if (
                    metrics.last_activity
                    and metrics.last_activity > timezone.now() - timedelta(days=7)
                ):
                    active_connections += 1
                    total_engagement += metrics.engagement_score

                    if conv_id.startswith("one_to_one"):
                        connection_types["individual"] += 1
                    elif conv_id.startswith("group"):
                        connection_types["group"] += 1
                    elif conv_id.startswith("chatbot"):
                        connection_types["ai_support"] += 1

            if active_connections > 0:
                avg_engagement = total_engagement / active_connections
                # Support network strength based on number of connections and engagement
                result.support_network_strength = min(
                    (active_connections * 0.3 + avg_engagement * 0.7), 5.0
                )

            result.social_connections = dict(connection_types)

        except Exception as e:
            self.logger.error(f"Error analyzing support network: {str(e)}")

    def _generate_insights(self, result: MessagingAnalysisResult):
        """Generate insights and recommendations based on analysis"""
        try:
            insights = []
            recommendations = []

            # Communication frequency insights
            if result.total_messages > 0:
                if result.avg_messages_per_conversation < 5:
                    insights.append(
                        "Low message volume per conversation may indicate limited engagement"
                    )
                    recommendations.append(
                        "Encourage deeper conversations with support network"
                    )
                elif result.avg_messages_per_conversation > 20:
                    insights.append(
                        "High engagement in conversations shows active communication"
                    )

            # Sentiment insights
            if result.overall_sentiment < -0.3:
                insights.append(
                    "Overall communication sentiment is negative, indicating potential distress"
                )
                recommendations.append(
                    "Consider increasing positive social interactions"
                )
            elif result.overall_sentiment > 0.3:
                insights.append(
                    "Positive communication patterns indicate good emotional state"
                )

            # Support network insights
            if result.support_network_strength < 2.0:
                insights.append("Limited support network may indicate social isolation")
                recommendations.append(
                    "Consider joining support groups or increasing social activities"
                )
            elif result.support_network_strength > 4.0:
                insights.append(
                    "Strong support network provides good emotional foundation"
                )

            # Chatbot effectiveness
            if result.chatbot_interactions > 0:
                if result.chatbot_effectiveness < 0.3:
                    insights.append(
                        "Low chatbot engagement suggests need for improved AI interactions"
                    )
                    recommendations.append(
                        "Review chatbot conversation flows and responses"
                    )
                elif result.chatbot_effectiveness > 0.7:
                    insights.append(
                        "High chatbot effectiveness shows good AI support utilization"
                    )

            # Crisis indicators
            if result.crisis_indicators:
                insights.append(
                    f"Detected {len(result.crisis_indicators)} potential crisis indicators"
                )
                recommendations.append(
                    "Immediate follow-up with mental health professional recommended"
                )

            # Response time patterns
            if result.response_time_patterns.get("average", 0) > 24:
                insights.append(
                    "Delayed response times may indicate reduced social engagement"
                )
                recommendations.append(
                    "Encourage more timely communication with support network"
                )

            result.insights = insights
            result.recommendations = recommendations

        except Exception as e:
            self.logger.error(f"Error generating insights: {str(e)}")

    def _extract_therapeutic_keywords(self, content: str) -> List[str]:
        """Extract therapeutic keywords from content"""
        if not content:
            return []

        content_lower = content.lower()
        found_keywords = []

        for category, keywords in self.therapeutic_keywords.items():
            for keyword in keywords:
                if keyword in content_lower:
                    found_keywords.append(f"{category}:{keyword}")

        return found_keywords

    def _calculate_sentiment_score(self, content: str) -> float:
        """Calculate simple sentiment score for content"""
        if not content:
            return 0.0

        # Simple sentiment analysis based on keyword presence
        positive_words = [
            "happy",
            "good",
            "better",
            "great",
            "wonderful",
            "amazing",
            "love",
            "joy",
            "excited",
            "grateful",
        ]
        negative_words = [
            "sad",
            "bad",
            "worse",
            "terrible",
            "awful",
            "hate",
            "angry",
            "frustrated",
            "depressed",
            "anxious",
        ]

        content_lower = content.lower()
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)

        total_words = len(content.split())
        if total_words == 0:
            return 0.0

        # Normalize sentiment score between -1 and 1
        sentiment = (positive_count - negative_count) / max(total_words / 10, 1)
        return max(-1.0, min(1.0, sentiment))

    def _calculate_engagement_score(self, metrics: ConversationMetrics) -> float:
        """Calculate engagement score for a conversation"""
        score = 0.0

        # Message frequency contributes to engagement
        if metrics.message_count > 0:
            score += min(metrics.message_count / 10, 2.0)  # Max 2 points for frequency

        # Response time affects engagement (lower is better)
        if metrics.avg_response_time > 0:
            response_score = max(
                0, 2.0 - (metrics.avg_response_time / 12)
            )  # 12 hours baseline
            score += response_score

        # Therapeutic keyword presence indicates deeper engagement
        if metrics.therapeutic_keywords:
            score += min(
                len(metrics.therapeutic_keywords) / 5, 1.0
            )  # Max 1 point for therapeutic content

        return min(score, 5.0)  # Cap at 5.0


# Singleton instance
messaging_collection_service = MessagingCollectionService()
