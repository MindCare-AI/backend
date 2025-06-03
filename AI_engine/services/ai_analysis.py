# AI_engine/services/ai_analysis.py
from typing import Dict, Any, List
import logging
from django.conf import settings
import requests
from django.utils import timezone
from ..models import UserAnalysis, AIInsight

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """Service for handling AI analysis of therapy sessions and user data."""

    def __init__(self):
        self.api_key = getattr(settings, "AI_API_KEY", None)
        self.api_endpoint = getattr(settings, "AI_API_ENDPOINT", None)
        self.cache_timeout = getattr(
            settings, "AI_CACHE_TIMEOUT", 3600
        )  # 1 hour default
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"
        self.batch_size = settings.AI_ENGINE_SETTINGS["ANALYSIS_BATCH_SIZE"]
        self.max_period = settings.AI_ENGINE_SETTINGS["MAX_ANALYSIS_PERIOD"]
        self.min_data_points = settings.AI_ENGINE_SETTINGS["MIN_DATA_POINTS"]
        self.risk_threshold = settings.AI_ENGINE_SETTINGS["RISK_THRESHOLD"]

    def generate_text(self, prompt: str) -> Dict[str, Any]:
        """Generate text response using Ollama"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "text": result["response"],
                    "metadata": {
                        "model": self.model,
                        "finish_reason": result.get("done", True),
                    },
                }
            else:
                logger.error(
                    f"Ollama request failed with status {response.status_code}"
                )
                raise Exception(
                    f"Ollama request failed with status {response.status_code}"
                )

        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            raise Exception(f"Text generation failed: {str(e)}")

    def analyze_user_data(self, user, date_range=30) -> Dict[str, Any]:
        """Analyze user's data using AI data interface service and Ollama for insights"""
        try:
            # Import AI data interface service
            from .data_interface import ai_data_interface

            # Get AI-ready dataset through data interface
            dataset = ai_data_interface.get_ai_ready_dataset(user.id, date_range)

            # Check data quality and readiness
            quality_metrics = dataset.get("quality_metrics", {})
            if quality_metrics.get("overall_quality", 0.0) < 0.2:
                logger.warning(
                    f"Insufficient data quality for user {user.id} analysis: {quality_metrics}"
                )
                return self._create_default_analysis()

            # Prepare data for AI analysis from AI-ready dataset
            analysis_data = self._prepare_ai_ready_data_for_analysis(dataset)

            # Get analysis from Ollama
            analysis = self._analyze_with_ollama(analysis_data)

            # Store analysis results
            user_analysis = UserAnalysis.objects.create(
                user=user,
                mood_score=analysis.get("mood_score", 0),
                sentiment_score=analysis.get("sentiment_score", 0),
                dominant_emotions=analysis.get("emotions", []),
                topics_of_concern=analysis.get("topics", []),
                suggested_activities=analysis.get("activities", []),
                risk_factors=analysis.get("risks", {}),
                improvement_metrics=analysis.get("improvements", {}),
            )

            # Generate therapy recommendations based on analysis
            self._create_therapy_recommendations(user, analysis)

            # Enhanced integration tracking with datawarehouse metrics
            processing_metadata = dataset.get("processing_metadata", {})
            analysis.update(
                {
                    "data_sources_used": processing_metadata.get(
                        "data_sources_used", []
                    ),
                    "data_quality_score": quality_metrics.get("overall_quality", 0.0),
                    "completeness_score": quality_metrics.get("completeness", 0.0),
                    "collection_time": processing_metadata.get(
                        "collection_time_seconds", 0
                    ),
                    "analysis_readiness": quality_metrics.get(
                        "analysis_recommendation", "unknown"
                    ),
                    "datawarehouse_version": processing_metadata.get(
                        "processing_version", "unknown"
                    ),
                }
            )

            # Generate insights if needed
            if analysis.get("needs_attention"):
                AIInsight.objects.create(
                    user=user,
                    insight_type="risk_alert",
                    insight_data={
                        "risk_factors": analysis["risks"],
                        "suggested_actions": analysis["activities"],
                        "data_sources": analysis.get("unified_data_sources", []),
                    },
                    priority="high",
                )

            return {
                "analysis_id": user_analysis.id,
                "mood_score": user_analysis.mood_score,
                "sentiment_score": user_analysis.sentiment_score,
                "emotions": user_analysis.dominant_emotions,
                "topics": user_analysis.topics_of_concern,
                "activities": user_analysis.suggested_activities,
                "risks": user_analysis.risk_factors,
                "improvements": user_analysis.improvement_metrics,
                "needs_attention": analysis.get("needs_attention", False),
                "unified_data_integration": {
                    "sources_used": analysis.get("unified_data_sources", []),
                    "data_quality": analysis.get("data_quality_score", 0.5),
                    "specialized_services": analysis.get(
                        "specialized_services_available", 0
                    ),
                    "collection_time": analysis.get("collection_time", 0),
                },
                "analysis_metadata": {
                    "version": "v4.0_unified",
                    "date": timezone.now().isoformat(),
                    "period_days": date_range,
                    "model_used": self.model,
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing user data with unified service: {str(e)}")
            return self._create_default_analysis()

    def _create_therapy_recommendations(self, user, analysis: Dict):
        """Create therapy recommendations based on analysis results"""
        try:
            from ..models import TherapyRecommendation

            recommendations_created = 0

            # Always create at least one activity recommendation from the default activities
            activities = analysis.get(
                "activities", ["journaling", "physical_activity", "breathing_exercises"]
            )

            # Create recommendations based on suggested activities
            for activity in activities[:3]:  # Limit to 3 activities
                if activity and activity not in ["general", "neutral"]:
                    TherapyRecommendation.objects.create(
                        user=user,
                        recommendation_type="activity_suggestion",
                        recommendation_data={
                            "activity": activity,
                            "priority": "medium",
                            "estimated_duration": "15-30 minutes",
                            "reason": "Based on analysis of mood patterns and journal entries",
                            "description": f"Try {activity.replace('_', ' ')} to improve your wellbeing",
                        },
                        context_data={
                            "mood_score": analysis.get("mood_score", 5),
                            "emotions": analysis.get("emotions", ["neutral"]),
                            "analysis_date": timezone.now().isoformat(),
                            "trigger_reason": "routine_analysis",
                        },
                    )
                    recommendations_created += 1

            # Create a general coping strategy recommendation
            TherapyRecommendation.objects.create(
                user=user,
                recommendation_type="coping_strategy",
                recommendation_data={
                    "strategy": "Regular mood monitoring",
                    "description": "Continue tracking your mood and journal entries to maintain awareness of your mental health patterns",
                    "frequency": "Daily",
                    "benefits": [
                        "Self-awareness",
                        "Pattern recognition",
                        "Early intervention",
                    ],
                },
                context_data={
                    "mood_score": analysis.get("mood_score", 5),
                    "analysis_date": timezone.now().isoformat(),
                    "data_points": len(analysis.get("mood_data", []))
                    + len(analysis.get("journal_data", [])),
                },
            )
            recommendations_created += 1

            # Create intervention recommendations for concerning patterns
            topics = analysis.get("topics", [])
            emotions = analysis.get("emotions", [])

            # Check for stress/anxiety patterns
            if any(
                term in str(topics + emotions).lower()
                for term in ["stress", "anxiety", "worried", "nervous"]
            ):
                TherapyRecommendation.objects.create(
                    user=user,
                    recommendation_type="intervention",
                    recommendation_data={
                        "intervention": "Stress and anxiety management",
                        "techniques": [
                            "Deep breathing exercises (4-7-8 technique)",
                            "Progressive muscle relaxation",
                            "Mindfulness meditation",
                            "Regular physical exercise",
                        ],
                        "priority": "high",
                        "description": "Addressing detected stress and anxiety patterns",
                    },
                    context_data={
                        "detected_patterns": ["stress", "anxiety"],
                        "emotions": emotions,
                        "topics": topics,
                        "analysis_date": timezone.now().isoformat(),
                    },
                )
                recommendations_created += 1

            # Check for sleep-related issues
            if any(
                term in str(topics).lower()
                for term in ["sleep", "tired", "exhausted", "insomnia"]
            ):
                TherapyRecommendation.objects.create(
                    user=user,
                    recommendation_type="coping_strategy",
                    recommendation_data={
                        "strategy": "Sleep hygiene improvement",
                        "description": "Focus on establishing better sleep patterns for improved mental health",
                        "specific_actions": [
                            "Maintain consistent sleep schedule",
                            "Create relaxing bedtime routine",
                            "Limit screen time before bed",
                            "Avoid caffeine late in the day",
                        ],
                        "expected_outcome": "Better sleep quality and mood regulation",
                    },
                    context_data={
                        "triggered_by": "sleep_concerns_detected",
                        "analysis_date": timezone.now().isoformat(),
                        "concern_level": "medium",
                    },
                )
                recommendations_created += 1

            analysis["recommendations_created"] = recommendations_created
            logger.info(
                f"Created {recommendations_created} therapy recommendations for user {user.id}"
            )

        except Exception as e:
            logger.error(
                f"Error creating therapy recommendations: {str(e)}", exc_info=True
            )
            analysis["recommendations_created"] = 0

    def _get_health_metrics(self, user, days: int) -> List[Dict]:
        """Get user's health metrics for analysis"""
        # Implementation placeholder - would pull from health metrics model
        return []

    def _analyze_with_ollama(self, data: Dict) -> Dict:
        """Analyze AI-ready data with Ollama model"""
        # Create a comprehensive prompt from the AI-ready data
        prompt = self._create_ai_ready_analysis_prompt(data)

        try:
            response = self.generate_text(prompt)
            # Parse the response into structured analysis
            analysis = self._parse_analysis_response(response["text"])

            # Add AI-ready data context to analysis
            analysis["data_sources_used"] = data.get("data_sources", [])
            analysis["data_richness_score"] = (
                len(data.get("data_sources", [])) / 7.0
            )  # Max 7 sources
            analysis["data_quality_score"] = data.get("data_quality", {}).get(
                "overall_quality", 0.0
            )

            return analysis
        except Exception as e:
            logger.error(f"Error in AI-ready data analysis: {str(e)}")
            return self._create_default_analysis()

    def _create_ai_ready_analysis_prompt(self, data: Dict) -> str:
        """Create a comprehensive prompt for AI-ready data analysis from datawarehouse"""
        prompt = "Analyze the following AI-ready comprehensive user data and provide clinical insights:\n\n"

        # Add data quality context
        quality_metrics = data.get("data_quality", {})
        prompt += "Data Quality Assessment:\n"
        prompt += f"- Overall Quality: {quality_metrics.get('overall_quality', 0.0):.2f}/1.0\n"
        prompt += (
            f"- Data Completeness: {quality_metrics.get('completeness', 0.0):.2f}/1.0\n"
        )
        prompt += f"- Analysis Recommendation: {quality_metrics.get('analysis_recommendation', 'unknown')}\n\n"

        # Add data sources information
        data_sources = data.get("data_sources", [])
        prompt += f"Available Data Sources ({len(data_sources)}): {', '.join(data_sources)}\n\n"

        # Add mood analytics if available
        if data.get("mood_analytics"):
            mood_data = data["mood_analytics"]
            prompt += "Mood Analytics Summary:\n"
            if mood_data.get("average_mood"):
                prompt += f"- Average Mood: {mood_data['average_mood']:.2f}/10\n"
            if mood_data.get("mood_trend"):
                prompt += f"- Mood Trend: {mood_data['mood_trend']}\n"
            if mood_data.get("mood_volatility"):
                prompt += f"- Mood Volatility: {mood_data['mood_volatility']:.2f}\n"
            if mood_data.get("dominant_emotions"):
                prompt += f"- Dominant Emotions: {', '.join(mood_data['dominant_emotions'])}\n"
            prompt += "\n"

        # Add journal analytics if available
        if data.get("journal_analytics"):
            journal_data = data["journal_analytics"]
            prompt += "Journal Analytics Summary:\n"
            if journal_data.get("sentiment_trend"):
                prompt += f"- Sentiment Trend: {journal_data['sentiment_trend']}\n"
            if journal_data.get("key_themes"):
                prompt += f"- Key Themes: {', '.join(journal_data['key_themes'])}\n"
            if journal_data.get("emotional_patterns"):
                prompt += (
                    f"- Emotional Patterns: {journal_data['emotional_patterns']}\n"
                )
            if journal_data.get("writing_frequency"):
                prompt += f"- Writing Frequency: {journal_data['writing_frequency']}\n"
            prompt += "\n"

        # Add behavioral analytics if available
        if data.get("behavioral_analytics"):
            behavior_data = data["behavioral_analytics"]
            prompt += "Behavioral Analytics Summary:\n"
            if behavior_data.get("activity_patterns"):
                prompt += f"- Activity Patterns: {behavior_data['activity_patterns']}\n"
            if behavior_data.get("engagement_metrics"):
                prompt += f"- Engagement Level: {behavior_data['engagement_metrics']}\n"
            if behavior_data.get("usage_trends"):
                prompt += f"- Usage Trends: {behavior_data['usage_trends']}\n"
            prompt += "\n"

        # Add therapy session analytics if available
        if data.get("therapy_analytics"):
            therapy_data = data["therapy_analytics"]
            prompt += "Therapy Session Analytics:\n"
            if therapy_data.get("session_frequency"):
                prompt += f"- Session Frequency: {therapy_data['session_frequency']}\n"
            if therapy_data.get("progress_indicators"):
                prompt += (
                    f"- Progress Indicators: {therapy_data['progress_indicators']}\n"
                )
            if therapy_data.get("therapeutic_focus"):
                prompt += f"- Therapeutic Focus Areas: {', '.join(therapy_data.get('therapeutic_focus', []))}\n"
            prompt += "\n"

        # Add social interaction analytics if available
        if data.get("social_analytics"):
            social_data = data["social_analytics"]
            prompt += "Social Interaction Analytics:\n"
            if social_data.get("social_engagement"):
                prompt += (
                    f"- Social Engagement Level: {social_data['social_engagement']}\n"
                )
            if social_data.get("support_network"):
                prompt += (
                    f"- Support Network Quality: {social_data['support_network']}\n"
                )
            if social_data.get("interaction_patterns"):
                prompt += (
                    f"- Interaction Patterns: {social_data['interaction_patterns']}\n"
                )
            prompt += "\n"

        # Add health metrics if available
        if data.get("health_analytics"):
            health_data = data["health_analytics"]
            prompt += "Health & Wellness Analytics:\n"
            if health_data.get("sleep_patterns"):
                prompt += f"- Sleep Quality: {health_data['sleep_patterns']}\n"
            if health_data.get("medication_adherence"):
                prompt += (
                    f"- Medication Adherence: {health_data['medication_adherence']}\n"
                )
            if health_data.get("physical_activity"):
                prompt += (
                    f"- Physical Activity Level: {health_data['physical_activity']}\n"
                )
            prompt += "\n"

        # Add goals and achievements if available
        if data.get("goals_analytics"):
            goals_data = data["goals_analytics"]
            prompt += "Goals & Achievement Analytics:\n"
            if goals_data.get("goal_completion_rate"):
                prompt += f"- Goal Completion Rate: {goals_data['goal_completion_rate']:.2f}\n"
            if goals_data.get("active_goals"):
                prompt += f"- Active Goals: {goals_data['active_goals']}\n"
            if goals_data.get("achievement_patterns"):
                prompt += (
                    f"- Achievement Patterns: {goals_data['achievement_patterns']}\n"
                )
            prompt += "\n"

        # Add analysis instructions with enhanced clinical focus
        prompt += "CLINICAL ANALYSIS REQUIREMENTS:\n"
        prompt += "Based on this comprehensive AI-ready dataset, provide a structured clinical analysis with these fields:\n\n"
        prompt += "1. mood_score (0-10 scale):\n"
        prompt += "   - 0-2: Severe depression/distress\n"
        prompt += "   - 3-4: Moderate depression/low mood\n"
        prompt += "   - 5-6: Neutral/stable mood\n"
        prompt += "   - 7-8: Positive/good mood\n"
        prompt += "   - 9-10: Excellent/euphoric mood\n\n"

        prompt += "2. sentiment_score (-1.0 to 1.0):\n"
        prompt += "   - Negative (-1.0 to -0.3): Predominantly negative outlook\n"
        prompt += "   - Neutral (-0.3 to 0.3): Balanced perspective\n"
        prompt += "   - Positive (0.3 to 1.0): Predominantly positive outlook\n\n"

        prompt += "3. emotions (list of detected emotional states):\n"
        prompt += (
            "   - Primary emotions: joy, sadness, anger, fear, surprise, disgust\n"
        )
        prompt += "   - Secondary emotions: anxiety, depression, excitement, contentment, etc.\n\n"

        prompt += "4. topics (key areas of concern or focus):\n"
        prompt += "   - Therapeutic themes, life challenges, relationship issues, work stress, etc.\n\n"

        prompt += "5. activities (evidence-based therapeutic recommendations):\n"
        prompt += "   - Be specific: 'cognitive_behavioral_therapy', 'mindfulness_meditation',\n"
        prompt += "   - 'progressive_muscle_relaxation', 'journaling_exercises', 'social_connection'\n\n"

        prompt += "6. risks (clinical risk assessment):\n"
        prompt += "   - Include severity levels: low, moderate, high\n"
        prompt += (
            "   - Risk factors: self_harm, substance_use, social_isolation, etc.\n\n"
        )

        prompt += "7. improvements (positive changes and progress indicators):\n"
        prompt += "   - Areas showing measurable improvement based on data trends\n\n"

        prompt += "8. needs_attention (boolean):\n"
        prompt += (
            "   - True if immediate clinical attention or intervention is recommended\n"
        )
        prompt += (
            "   - Based on risk factors, mood severity, or concerning patterns\n\n"
        )

        prompt += "IMPORTANT CONSIDERATIONS:\n"
        prompt += f"- Data quality score: {quality_metrics.get('overall_quality', 0.0):.2f} (consider reliability)\n"
        prompt += f"- Data completeness: {quality_metrics.get('completeness', 0.0):.2f} (adjust confidence accordingly)\n"
        prompt += (
            "- Focus on evidence-based insights derived from available data sources\n"
        )
        prompt += "- Provide actionable, specific recommendations based on comprehensive data patterns\n"
        prompt += "- Consider temporal trends and patterns in the analysis\n"
        prompt += "- Weight recommendations based on data quality and completeness\n\n"

        return prompt

    def _create_unified_analysis_prompt(self, data: Dict) -> str:
        """Create a comprehensive prompt for unified data analysis"""
        prompt = (
            "Analyze the following comprehensive user data and provide insights:\n\n"
        )

        # Add specialized service insights
        if data.get("user_behavior"):
            prompt += "User Behavior Analytics:\n"
            behavior_data = data["user_behavior"]
            prompt += (
                f"- Activity patterns: {behavior_data.get('activity_patterns', {})}\n"
            )
            prompt += (
                f"- Engagement metrics: {behavior_data.get('engagement_metrics', {})}\n"
            )
            prompt += f"- Usage trends: {behavior_data.get('usage_trends', {})}\n\n"

        if data.get("mood_journal_insights"):
            prompt += "Mood & Journal Analytics:\n"
            mood_data = data["mood_journal_insights"]
            prompt += f"- Mood trends: {mood_data.get('mood_trends', {})}\n"
            prompt += (
                f"- Journal sentiment: {mood_data.get('sentiment_analysis', {})}\n"
            )
            prompt += (
                f"- Emotional patterns: {mood_data.get('emotional_patterns', {})}\n\n"
            )

        if data.get("therapy_sessions"):
            prompt += "Therapy Session Analytics:\n"
            therapy_data = data["therapy_sessions"]
            prompt += (
                f"- Session insights: {therapy_data.get('session_insights', {})}\n"
            )
            prompt += (
                f"- Progress indicators: {therapy_data.get('progress_metrics', {})}\n"
            )
            prompt += (
                f"- Therapeutic notes: {therapy_data.get('notes_analysis', {})}\n\n"
            )

        if data.get("social_interactions"):
            prompt += "Social Interaction Analytics:\n"
            social_data = data["social_interactions"]
            prompt += (
                f"- Social engagement: {social_data.get('engagement_analysis', {})}\n"
            )
            prompt += f"- Interaction patterns: {social_data.get('interaction_patterns', {})}\n"
            prompt += f"- Community involvement: {social_data.get('community_metrics', {})}\n\n"

        # Add legacy data if present
        if data.get("mood_logs"):
            prompt += "Direct Mood Logs:\n"
            for log in data["mood_logs"][:5]:  # Limit to 5 entries
                prompt += f"- Mood: {log.get('mood', 'N/A')}, Date: {log.get('timestamp', 'N/A')}\n"
            prompt += "\n"

        if data.get("journal_entries"):
            prompt += "Direct Journal Entries:\n"
            for entry in data["journal_entries"][:3]:  # Limit to 3 entries
                content = entry.get("content", "")[:100]  # Truncate long content
                prompt += f"- Entry: {content}..., Mood: {entry.get('mood', 'N/A')}\n"
            prompt += "\n"

        # Add analysis instructions
        prompt += "Based on this comprehensive data, provide a structured analysis with these fields:\n"
        prompt += (
            "1. mood_score (0-10, where 0 is very negative, 10 is very positive)\n"
        )
        prompt += "2. sentiment_score (-1 to 1, where -1 is negative, 1 is positive)\n"
        prompt += "3. emotions (list of key emotions detected)\n"
        prompt += "4. topics (list of topics of concern or focus areas)\n"
        prompt += "5. activities (specific therapeutic activities recommended)\n"
        prompt += "6. risks (any risk factors noted with severity levels)\n"
        prompt += "7. improvements (areas showing improvement)\n"
        prompt += (
            "8. needs_attention (boolean for whether immediate attention is needed)\n\n"
        )
        prompt += "Focus on providing actionable, specific recommendations based on the comprehensive data patterns.\n"
        prompt += f"Data sources available: {', '.join(data.get('data_sources', []))}\n"

        return prompt

    def _create_analysis_prompt(self, data: Dict) -> str:
        """Create a prompt for user data analysis"""
        prompt = "Analyze the following user data and provide insights:\n\n"

        if data.get("mood_logs"):
            prompt += "Mood logs:\n"
            for log in data["mood_logs"][:5]:  # Limit to 5 entries
                prompt += f"- Mood: {log['mood']}, Date: {log['timestamp']}\n"

        if data.get("journal_entries"):
            prompt += "\nJournal entries:\n"
            for entry in data["journal_entries"][:3]:  # Limit to 3 entries
                prompt += (
                    f"- Entry: {entry['content'][:100]}..., Mood: {entry['mood']}\n"
                )

        prompt += "\nProvide a structured analysis with these fields:\n"
        prompt += (
            "1. mood_score (0-10, where 0 is very negative, 10 is very positive)\n"
        )
        prompt += "2. sentiment_score (-1 to 1, where -1 is negative, 1 is positive)\n"
        prompt += "3. emotions (list of key emotions detected)\n"
        prompt += "4. topics (list of topics of concern or focus areas)\n"
        prompt += "5. activities (specific therapeutic activities recommended - be specific like 'mindfulness_meditation', 'journaling', 'physical_exercise', 'breathing_exercises')\n"
        prompt += "6. risks (any risk factors noted with severity levels)\n"
        prompt += "7. improvements (areas showing improvement)\n"
        prompt += (
            "8. needs_attention (boolean for whether immediate attention is needed)\n\n"
        )
        prompt += "Focus on providing actionable, specific recommendations based on the user's mood patterns and journal content."

        return prompt

    def _parse_analysis_response(self, response_text: str) -> Dict:
        """Parse AI response into structured analysis"""
        analysis = {
            "mood_score": 5,  # Default values
            "sentiment_score": 0,
            "emotions": ["neutral"],
            "topics": [],
            "activities": ["journaling", "physical_activity", "breathing_exercises"],
            "risks": {},
            "improvements": {},
            "needs_attention": False,
        }

        try:
            import re

            # Try to parse mood score
            mood_match = re.search(
                r"mood_score[:\s]*(\d+)", response_text, re.IGNORECASE
            )
            if mood_match:
                analysis["mood_score"] = int(mood_match.group(1))

            # Try to parse emotions
            emotions_match = re.search(
                r"emotions[:\s]*\[(.*?)\]", response_text, re.IGNORECASE | re.DOTALL
            )
            if emotions_match:
                emotions_str = emotions_match.group(1)
                emotions = [
                    e.strip().strip("\"'") for e in emotions_str.split(",") if e.strip()
                ]
                if emotions:
                    analysis["emotions"] = emotions

            # Try to parse activities
            activities_match = re.search(
                r"activities[:\s]*\[(.*?)\]", response_text, re.IGNORECASE | re.DOTALL
            )
            if activities_match:
                activities_str = activities_match.group(1)
                activities = [
                    a.strip().strip("\"'")
                    for a in activities_str.split(",")
                    if a.strip()
                ]
                if activities:
                    analysis["activities"] = activities

            # Check for attention keywords
            attention_keywords = [
                "urgent",
                "concerning",
                "risk",
                "danger",
                "immediate",
                "crisis",
            ]
            if any(keyword in response_text.lower() for keyword in attention_keywords):
                analysis["needs_attention"] = True

        except Exception as e:
            logger.error(f"Error parsing analysis response: {str(e)}")

        return analysis

    def _create_default_analysis(self) -> Dict:
        """Create a default analysis when data is insufficient"""
        return {
            "mood_score": 5,
            "sentiment_score": 0,
            "emotions": ["neutral"],
            "topics": [],
            "activities": ["journaling", "physical activity"],
            "risks": {},
            "improvements": {},
            "needs_attention": False,
        }

    def analyze_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a therapy session using AI.

        Args:
            session_data: Dictionary containing session information

        Returns:
            Dictionary containing analysis results
        """
        try:
            if not self.api_key or not self.api_endpoint:
                logger.error("AI service not properly configured")
                return {"error": "AI service configuration missing"}

            # Prepare the data for analysis
            analysis_data = self._prepare_session_data(session_data)

            # Make API request
            response = requests.post(
                f"{self.api_endpoint}/analyze",
                json=analysis_data,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"AI analysis failed: {response.text}")
                return {"error": "Analysis failed", "status": response.status_code}

        except Exception as e:
            logger.error(f"Error in analyze_session: {str(e)}")
            return {"error": str(e)}

    def _prepare_session_data(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare session data for AI analysis."""
        return {
            "session_id": session_data.get("id"),
            "timestamp": timezone.now().isoformat(),
            "content": session_data.get("content", ""),
            "metadata": session_data.get("metadata", {}),
        }

    def get_recommendations(self, user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get AI-powered recommendations for a user.

        Args:
            user_data: Dictionary containing user information

        Returns:
            List of recommendation dictionaries
        """
        try:
            if not self.api_key or not self.api_endpoint:
                logger.error("AI service not properly configured")
                return []

            response = requests.post(
                f"{self.api_endpoint}/recommendations",
                json=user_data,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            if response.status_code == 200:
                return response.json().get("recommendations", [])
            else:
                logger.error(f"Failed to get recommendations: {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error in get_recommendations: {str(e)}")
            return []

    def _has_sufficient_unified_data(self, unified_snapshot) -> bool:
        """Check if unified snapshot has sufficient data for analysis"""
        data_sources = 0

        # Check specialized service data
        if unified_snapshot.user_behavior_analytics:
            data_sources += 1
        if unified_snapshot.mood_journal_analytics:
            data_sources += 1
        if unified_snapshot.therapist_session_analytics:
            data_sources += 1
        if unified_snapshot.feeds_analytics:
            data_sources += 1

        # Check legacy data
        if unified_snapshot.legacy_mood_data and unified_snapshot.legacy_mood_data.get(
            "mood_logs"
        ):
            data_sources += 1
        if (
            unified_snapshot.legacy_journal_data
            and unified_snapshot.legacy_journal_data.get("journal_entries")
        ):
            data_sources += 1
        if (
            unified_snapshot.legacy_messaging_data
            and unified_snapshot.legacy_messaging_data.get("messages")
        ):
            data_sources += 1

        # Need at least 1 data source with meaningful data
        return data_sources >= 1

    def _prepare_unified_data_for_analysis(self, unified_snapshot) -> Dict[str, Any]:
        """Convert unified snapshot to format suitable for AI analysis"""
        analysis_data = {
            "user_id": unified_snapshot.user_id,
            "collection_date": unified_snapshot.collection_date.isoformat(),
            "period_days": unified_snapshot.period_days,
            "data_sources": [],
        }

        # Process specialized service data
        if unified_snapshot.user_behavior_analytics:
            analysis_data["user_behavior"] = unified_snapshot.user_behavior_analytics
            analysis_data["data_sources"].append("user_behavior_service")

        if unified_snapshot.mood_journal_analytics:
            analysis_data["mood_journal_insights"] = (
                unified_snapshot.mood_journal_analytics
            )
            analysis_data["data_sources"].append("mood_journal_service")

        if unified_snapshot.therapist_session_analytics:
            analysis_data["therapy_sessions"] = (
                unified_snapshot.therapist_session_analytics
            )
            analysis_data["data_sources"].append("therapist_session_service")

        if unified_snapshot.feeds_analytics:
            analysis_data["social_interactions"] = unified_snapshot.feeds_analytics
            analysis_data["data_sources"].append("feeds_service")

        # Process legacy data for backwards compatibility
        if unified_snapshot.legacy_mood_data:
            analysis_data["mood_logs"] = unified_snapshot.legacy_mood_data.get(
                "mood_logs", []
            )
            analysis_data["data_sources"].append("legacy_mood")

        if unified_snapshot.legacy_journal_data:
            analysis_data["journal_entries"] = unified_snapshot.legacy_journal_data.get(
                "journal_entries", []
            )
            analysis_data["data_sources"].append("legacy_journal")

        if unified_snapshot.legacy_messaging_data:
            analysis_data["messaging_data"] = unified_snapshot.legacy_messaging_data
            analysis_data["data_sources"].append("legacy_messaging")

        if unified_snapshot.legacy_appointment_data:
            analysis_data["appointment_data"] = unified_snapshot.legacy_appointment_data
            analysis_data["data_sources"].append("legacy_appointments")

        # Add metadata
        analysis_data["collection_metadata"] = (
            unified_snapshot.collection_metadata or {}
        )

        return analysis_data

    def _prepare_ai_ready_data_for_analysis(
        self, dataset: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare AI-ready dataset for Ollama analysis
        Transforms datawarehouse format into analysis-ready structure
        """
        try:
            analysis_data = {"data_sources": [], "comprehensive_insights": {}}

            # Extract mood analytics
            mood_analytics = dataset.get("mood_analytics", {})
            if mood_analytics and mood_analytics.get("status") != "error":
                analysis_data["mood_analytics"] = mood_analytics
                analysis_data["data_sources"].append("mood_analytics")

            # Extract journal analytics
            journal_analytics = dataset.get("journal_analytics", {})
            if journal_analytics and journal_analytics.get("status") != "error":
                analysis_data["journal_analytics"] = journal_analytics
                analysis_data["data_sources"].append("journal_analytics")

            # Extract behavioral patterns
            behavioral_analytics = dataset.get("behavioral_analytics", {})
            if behavioral_analytics and behavioral_analytics.get("status") != "error":
                analysis_data["behavioral_analytics"] = behavioral_analytics
                analysis_data["data_sources"].append("behavioral_analytics")

            # Extract communication metrics
            communication_analytics = dataset.get("communication_analytics", {})
            if (
                communication_analytics
                and communication_analytics.get("status") != "error"
            ):
                analysis_data["communication_analytics"] = communication_analytics
                analysis_data["data_sources"].append("communication_analytics")

            # Extract therapy session data
            therapy_analytics = dataset.get("therapy_session_analytics", {})
            if therapy_analytics and therapy_analytics.get("status") != "error":
                analysis_data["therapy_analytics"] = therapy_analytics
                analysis_data["data_sources"].append("therapy_analytics")

            # Extract social engagement data
            social_analytics = dataset.get("social_analytics", {})
            if social_analytics and social_analytics.get("status") != "error":
                analysis_data["social_analytics"] = social_analytics
                analysis_data["data_sources"].append("social_analytics")

            # Extract cross-domain insights
            processed_insights = dataset.get("processed_insights", {})
            if processed_insights and processed_insights.get("status") != "error":
                analysis_data["processed_insights"] = processed_insights
                analysis_data["data_sources"].append("processed_insights")

            # Add quality metrics for context
            quality_metrics = dataset.get("quality_metrics", {})
            analysis_data["data_quality"] = {
                "overall_quality": quality_metrics.get("overall_quality", 0.0),
                "completeness": quality_metrics.get("completeness", 0.0),
                "domain_scores": quality_metrics.get("domain_scores", {}),
                "analysis_recommendation": quality_metrics.get(
                    "analysis_recommendation", "unknown"
                ),
            }

            # Add processing metadata
            processing_metadata = dataset.get("processing_metadata", {})
            analysis_data["metadata"] = {
                "collection_timestamp": processing_metadata.get("collection_timestamp"),
                "processing_version": processing_metadata.get(
                    "processing_version", "unknown"
                ),
                "data_sources_used": processing_metadata.get("data_sources_used", []),
                "cached": processing_metadata.get("cached", False),
            }

            logger.info(
                f"Prepared AI-ready data with {len(analysis_data['data_sources'])} data sources"
            )
            return analysis_data

        except Exception as e:
            logger.error(f"Error preparing AI-ready data for analysis: {e}")
            return {
                "data_sources": [],
                "error": str(e),
                "mood_analytics": {"status": "error"},
                "journal_analytics": {"status": "error"},
            }

    def _create_ai_ready_analysis_prompt(self, data: Dict) -> str:
        """Create a comprehensive prompt for AI-ready data analysis from datawarehouse"""
        prompt = "Analyze the following AI-ready comprehensive user data and provide clinical insights:\n\n"

        # Add data quality context
        quality_metrics = data.get("data_quality", {})
        prompt += "Data Quality Assessment:\n"
        prompt += f"- Overall Quality: {quality_metrics.get('overall_quality', 0.0):.2f}/1.0\n"
        prompt += (
            f"- Data Completeness: {quality_metrics.get('completeness', 0.0):.2f}/1.0\n"
        )
        prompt += f"- Analysis Recommendation: {quality_metrics.get('analysis_recommendation', 'unknown')}\n\n"

        # Add data sources information
        data_sources = data.get("data_sources", [])
        prompt += f"Available Data Sources ({len(data_sources)}): {', '.join(data_sources)}\n\n"

        # Add mood analytics if available
        if data.get("mood_analytics"):
            mood_data = data["mood_analytics"]
            prompt += "Mood Analytics Summary:\n"
            if mood_data.get("average_mood"):
                prompt += f"- Average Mood: {mood_data['average_mood']:.2f}/10\n"
            if mood_data.get("mood_trend"):
                prompt += f"- Mood Trend: {mood_data['mood_trend']}\n"
            if mood_data.get("mood_volatility"):
                prompt += f"- Mood Volatility: {mood_data['mood_volatility']:.2f}\n"
            if mood_data.get("dominant_emotions"):
                prompt += f"- Dominant Emotions: {', '.join(mood_data['dominant_emotions'])}\n"
            prompt += "\n"

        # Add journal analytics if available
        if data.get("journal_analytics"):
            journal_data = data["journal_analytics"]
            prompt += "Journal Analytics Summary:\n"
            if journal_data.get("sentiment_trend"):
                prompt += f"- Sentiment Trend: {journal_data['sentiment_trend']}\n"
            if journal_data.get("key_themes"):
                prompt += f"- Key Themes: {', '.join(journal_data['key_themes'])}\n"
            if journal_data.get("emotional_patterns"):
                prompt += (
                    f"- Emotional Patterns: {journal_data['emotional_patterns']}\n"
                )
            if journal_data.get("writing_frequency"):
                prompt += f"- Writing Frequency: {journal_data['writing_frequency']}\n"
            prompt += "\n"

        # Add behavioral analytics if available
        if data.get("behavioral_analytics"):
            behavior_data = data["behavioral_analytics"]
            prompt += "Behavioral Analytics Summary:\n"
            if behavior_data.get("activity_patterns"):
                prompt += f"- Activity Patterns: {behavior_data['activity_patterns']}\n"
            if behavior_data.get("engagement_metrics"):
                prompt += f"- Engagement Level: {behavior_data['engagement_metrics']}\n"
            if behavior_data.get("usage_trends"):
                prompt += f"- Usage Trends: {behavior_data['usage_trends']}\n"
            prompt += "\n"

        # Add therapy session analytics if available
        if data.get("therapy_analytics"):
            therapy_data = data["therapy_analytics"]
            prompt += "Therapy Session Analytics:\n"
            if therapy_data.get("session_frequency"):
                prompt += f"- Session Frequency: {therapy_data['session_frequency']}\n"
            if therapy_data.get("progress_indicators"):
                prompt += (
                    f"- Progress Indicators: {therapy_data['progress_indicators']}\n"
                )
            if therapy_data.get("therapeutic_focus"):
                prompt += f"- Therapeutic Focus Areas: {', '.join(therapy_data.get('therapeutic_focus', []))}\n"
            prompt += "\n"

        # Add social interaction analytics if available
        if data.get("social_analytics"):
            social_data = data["social_analytics"]
            prompt += "Social Interaction Analytics:\n"
            if social_data.get("social_engagement"):
                prompt += (
                    f"- Social Engagement Level: {social_data['social_engagement']}\n"
                )
            if social_data.get("support_network"):
                prompt += (
                    f"- Support Network Quality: {social_data['support_network']}\n"
                )
            if social_data.get("interaction_patterns"):
                prompt += (
                    f"- Interaction Patterns: {social_data['interaction_patterns']}\n"
                )
            prompt += "\n"

        # Add health metrics if available
        if data.get("health_analytics"):
            health_data = data["health_analytics"]
            prompt += "Health & Wellness Analytics:\n"
            if health_data.get("sleep_patterns"):
                prompt += f"- Sleep Quality: {health_data['sleep_patterns']}\n"
            if health_data.get("medication_adherence"):
                prompt += (
                    f"- Medication Adherence: {health_data['medication_adherence']}\n"
                )
            if health_data.get("physical_activity"):
                prompt += (
                    f"- Physical Activity Level: {health_data['physical_activity']}\n"
                )
            prompt += "\n"

        # Add goals and achievements if available
        if data.get("goals_analytics"):
            goals_data = data["goals_analytics"]
            prompt += "Goals & Achievement Analytics:\n"
            if goals_data.get("goal_completion_rate"):
                prompt += f"- Goal Completion Rate: {goals_data['goal_completion_rate']:.2f}\n"
            if goals_data.get("active_goals"):
                prompt += f"- Active Goals: {goals_data['active_goals']}\n"
            if goals_data.get("achievement_patterns"):
                prompt += (
                    f"- Achievement Patterns: {goals_data['achievement_patterns']}\n"
                )
            prompt += "\n"

        # Add analysis instructions with enhanced clinical focus
        prompt += "CLINICAL ANALYSIS REQUIREMENTS:\n"
        prompt += "Based on this comprehensive AI-ready dataset, provide a structured clinical analysis with these fields:\n\n"
        prompt += "1. mood_score (0-10 scale):\n"
        prompt += "   - 0-2: Severe depression/distress\n"
        prompt += "   - 3-4: Moderate depression/low mood\n"
        prompt += "   - 5-6: Neutral/stable mood\n"
        prompt += "   - 7-8: Positive/good mood\n"
        prompt += "   - 9-10: Excellent/euphoric mood\n\n"

        prompt += "2. sentiment_score (-1.0 to 1.0):\n"
        prompt += "   - Negative (-1.0 to -0.3): Predominantly negative outlook\n"
        prompt += "   - Neutral (-0.3 to 0.3): Balanced perspective\n"
        prompt += "   - Positive (0.3 to 1.0): Predominantly positive outlook\n\n"

        prompt += "3. emotions (list of detected emotional states):\n"
        prompt += (
            "   - Primary emotions: joy, sadness, anger, fear, surprise, disgust\n"
        )
        prompt += "   - Secondary emotions: anxiety, depression, excitement, contentment, etc.\n\n"

        prompt += "4. topics (key areas of concern or focus):\n"
        prompt += "   - Therapeutic themes, life challenges, relationship issues, work stress, etc.\n\n"

        prompt += "5. activities (evidence-based therapeutic recommendations):\n"
        prompt += "   - Be specific: 'cognitive_behavioral_therapy', 'mindfulness_meditation',\n"
        prompt += "   - 'progressive_muscle_relaxation', 'journaling_exercises', 'social_connection'\n\n"

        prompt += "6. risks (clinical risk assessment):\n"
        prompt += "   - Include severity levels: low, moderate, high\n"
        prompt += (
            "   - Risk factors: self_harm, substance_use, social_isolation, etc.\n\n"
        )

        prompt += "7. improvements (positive changes and progress indicators):\n"
        prompt += "   - Areas showing measurable improvement based on data trends\n\n"

        prompt += "8. needs_attention (boolean):\n"
        prompt += (
            "   - True if immediate clinical attention or intervention is recommended\n"
        )
        prompt += (
            "   - Based on risk factors, mood severity, or concerning patterns\n\n"
        )

        prompt += "IMPORTANT CONSIDERATIONS:\n"
        prompt += f"- Data quality score: {quality_metrics.get('overall_quality', 0.0):.2f} (consider reliability)\n"
        prompt += f"- Data completeness: {quality_metrics.get('completeness', 0.0):.2f} (adjust confidence accordingly)\n"
        prompt += (
            "- Focus on evidence-based insights derived from available data sources\n"
        )
        prompt += "- Provide actionable, specific recommendations based on comprehensive data patterns\n"
        prompt += "- Consider temporal trends and patterns in the analysis\n"
        prompt += "- Weight recommendations based on data quality and completeness\n\n"

        return prompt


# Create a singleton instance for use throughout the application
ai_service = AIAnalysisService()
