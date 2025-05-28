# AI_engine/services/communication_analysis.py
from typing import Dict, List, Any, Optional
import logging
import requests
import json
import numpy as np
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class CommunicationAnalysisService:
    """Service for analyzing communication patterns in therapeutic relationships"""

    def __init__(self):
        self.base_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
        self.model = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "DEFAULT_MODEL", "mistral"
        )
        self.cache_timeout = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "CACHE_TIMEOUT", 900
        )
        self.max_prompt_length = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "MAX_PROMPT_LENGTH", 4000
        )

    def analyze_patterns(self, user, days: int = 30) -> Dict[str, Any]:
        """Analyze communication patterns for a user"""
        cache_key = f"comm_patterns_{user.id}_{days}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # Collect communication data
            communication_data = self._collect_communication_data(user, days)
            
            if not communication_data["has_data"]:
                return self._create_no_data_response()

            # Analyze patterns
            patterns = self._analyze_communication_patterns(communication_data)
            
            # Use AI for deeper insights
            ai_insights = self._generate_ai_insights(patterns)
            
            # Combine results
            result = {
                "user_id": user.id,
                "analysis_period_days": days,
                "communication_data": communication_data,
                "patterns": patterns,
                "ai_insights": ai_insights,
                "analyzed_at": timezone.now().isoformat(),
            }
            
            # Cache the result
            cache.set(cache_key, result, self.cache_timeout)
            return result

        except Exception as e:
            logger.error(f"Error analyzing communication patterns: {str(e)}", exc_info=True)
            return self._create_error_response(str(e))

    def get_therapeutic_relationship_data(self, user) -> Dict[str, Any]:
        """Get therapeutic relationship analysis data"""
        cache_key = f"therapeutic_relationship_{user.id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # For therapists, analyze their relationships with patients
            if hasattr(user, 'therapist_profile') and user.therapist_profile:
                relationship_data = self._analyze_therapist_relationships(user)
            else:
                # For patients, analyze their relationship with therapists
                relationship_data = self._analyze_patient_relationships(user)

            if not relationship_data["has_relationships"]:
                return self._create_no_relationship_response()

            # Cache the result
            cache.set(cache_key, relationship_data, self.cache_timeout)
            return relationship_data

        except Exception as e:
            logger.error(f"Error getting therapeutic relationship data: {str(e)}", exc_info=True)
            return self._create_error_response(str(e))

    def _collect_communication_data(self, user, days: int) -> Dict[str, Any]:
        """Collect communication data from various sources"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        data = {
            "has_data": False,
            "chatbot_messages": [],
            "appointment_communications": [],
            "journal_entries": [],
            "mood_logs": [],
            "total_interactions": 0,
        }

        try:
            # Collect chatbot messages
            from chatbot.models import ChatMessage
            chatbot_messages = ChatMessage.objects.filter(
                user=user,
                timestamp__range=(start_date, end_date)  # Changed from created_at to timestamp
            ).order_by('-timestamp')[:50]  # Also change the order_by field
            
            data["chatbot_messages"] = [
                {
                    "content": msg.content[:200],  # Limit content length
                    "is_from_user": msg.is_from_user,
                    "created_at": msg.created_at.isoformat(),
                    "message_type": getattr(msg, "message_type", "text"),
                    "response_time": getattr(msg, "response_time", None),
                }
                for msg in chatbot_messages
            ]
            
            # Collect journal entries for communication style analysis
            from journal.models import JournalEntry
            journal_entries = JournalEntry.objects.filter(
                user=user,
                created_at__range=(start_date, end_date)
            ).order_by('-created_at')[:20]  # Limit to recent 20 entries
            
            data["journal_entries"] = [
                {
                    "content": entry.content[:300],  # Limit content length
                    "mood": entry.mood,
                    "created_at": entry.created_at.isoformat(),
                    "word_count": len(entry.content.split()),
                }
                for entry in journal_entries
            ]
            
            # Collect mood logs for emotional context
            from mood.models import MoodLog
            mood_logs = MoodLog.objects.filter(
                user=user,
                logged_at__range=(start_date, end_date)
            ).order_by('-logged_at')[:30]  # Limit to recent 30 logs
            
            data["mood_logs"] = [
                {
                    "mood_rating": log.mood_rating,
                    "logged_at": log.logged_at.isoformat(),
                    "activities": getattr(log, "activities", []),
                    "notes": getattr(log, "notes", ""),
                }
                for log in mood_logs
            ]
            
            # Try to collect appointment data if available
            try:
                from appointments.models import Appointment
                appointments = Appointment.objects.filter(
                    patient=user,
                    scheduled_time__range=(start_date, end_date)
                ).order_by('-scheduled_time')[:10]
                
                data["appointment_communications"] = [
                    {
                        "status": appt.status,
                        "scheduled_time": appt.scheduled_time.isoformat(),
                        "therapist": getattr(appt.therapist, "username", "Unknown"),
                        "notes": getattr(appt, "notes", ""),
                    }
                    for appt in appointments
                ]
            except Exception:
                # Appointments app might not be available
                pass

            # Calculate totals
            data["total_interactions"] = (
                len(data["chatbot_messages"]) +
                len(data["journal_entries"]) +
                len(data["mood_logs"]) +
                len(data["appointment_communications"])
            )
            
            data["has_data"] = data["total_interactions"] > 0
            
            return data

        except Exception as e:
            logger.error(f"Error collecting communication data: {str(e)}")
            return data

    def _analyze_communication_patterns(self, communication_data: Dict) -> Dict[str, Any]:
        """Analyze patterns in communication data"""
        patterns = {
            "communication_frequency": self._analyze_frequency_patterns(communication_data),
            "emotional_expression": self._analyze_emotional_patterns(communication_data),
            "content_analysis": self._analyze_content_patterns(communication_data),
            "temporal_patterns": self._analyze_temporal_patterns(communication_data),
            "engagement_metrics": self._calculate_engagement_metrics(communication_data),
        }
        
        return patterns

    def _analyze_frequency_patterns(self, data: Dict) -> Dict[str, Any]:
        """Analyze frequency of different types of communications"""
        total_days = 30  # Default analysis period
        
        return {
            "chatbot_frequency": len(data["chatbot_messages"]) / total_days,
            "journal_frequency": len(data["journal_entries"]) / total_days,
            "mood_logging_frequency": len(data["mood_logs"]) / total_days,
            "appointment_frequency": len(data["appointment_communications"]) / total_days,
            "overall_activity": data["total_interactions"] / total_days,
        }

    def _analyze_emotional_patterns(self, data: Dict) -> Dict[str, Any]:
        """Analyze emotional expression patterns"""
        emotional_indicators = {
            "positive_words": 0,
            "negative_words": 0,
            "anxiety_indicators": 0,
            "progress_indicators": 0,
            "help_seeking": 0,
        }
        
        # Define keyword patterns
        patterns = {
            "positive_words": [r"\bhappy\b", r"\bgood\b", r"\bgreat\b", r"\bbetter\b", r"\bimproved\b"],
            "negative_words": [r"\bsad\b", r"\bbad\b", r"\bawful\b", r"\bworse\b", r"\bterrible\b"],
            "anxiety_indicators": [r"\banxious\b", r"\bworried\b", r"\bstressed\b", r"\bnervous\b"],
            "progress_indicators": [r"\bprogress\b", r"\blearned\b", r"\bgrew\b", r"\bimproved\b"],
            "help_seeking": [r"\bhelp\b", r"\bsupport\b", r"\badvice\b", r"\bguidance\b"],
        }
        
        # Analyze chatbot messages
        for message in data["chatbot_messages"]:
            if message["is_from_user"]:
                content = message["content"].lower()
                for category, pattern_list in patterns.items():
                    for pattern in pattern_list:
                        emotional_indicators[category] += len(re.findall(pattern, content))
        
        # Analyze journal entries
        for entry in data["journal_entries"]:
            content = entry["content"].lower()
            for category, pattern_list in patterns.items():
                for pattern in pattern_list:
                    emotional_indicators[category] += len(re.findall(pattern, content))
        
        # Calculate emotional balance
        total_emotional_words = sum(emotional_indicators.values())
        if total_emotional_words > 0:
            emotional_balance = {
                category: count / total_emotional_words
                for category, count in emotional_indicators.items()
            }
        else:
            emotional_balance = {category: 0.0 for category in emotional_indicators.keys()}
        
        return {
            "emotional_indicators": emotional_indicators,
            "emotional_balance": emotional_balance,
            "overall_sentiment": self._calculate_overall_sentiment(emotional_indicators),
        }

    def _calculate_overall_sentiment(self, indicators: Dict) -> str:
        """Calculate overall sentiment from emotional indicators"""
        positive_score = indicators["positive_words"] + indicators["progress_indicators"]
        negative_score = indicators["negative_words"] + indicators["anxiety_indicators"]
        
        if positive_score > negative_score * 1.2:
            return "positive"
        elif negative_score > positive_score * 1.2:
            return "negative"
        else:
            return "neutral"

    def _analyze_content_patterns(self, data: Dict) -> Dict[str, Any]:
        """Analyze content patterns and themes"""
        themes = defaultdict(int)
        
        # Define theme keywords
        theme_keywords = {
            "therapy": [r"\btherapy\b", r"\bsession\b", r"\bcounseling\b"],
            "relationships": [r"\bfamily\b", r"\bfriend\b", r"\bpartner\b", r"\brelationship\b"],
            "work_stress": [r"\bwork\b", r"\bjob\b", r"\bstress\b", r"\bboss\b"],
            "mental_health": [r"\bdepression\b", r"\banxiety\b", r"\bmental health\b"],
            "self_care": [r"\bself care\b", r"\bmeditation\b", r"\bexercise\b", r"\brelax\b"],
            "goals": [r"\bgoal\b", r"\bplan\b", r"\bfuture\b", r"\bprogress\b"],
        }
        
        all_content = []
        
        # Collect all text content
        for message in data["chatbot_messages"]:
            if message["is_from_user"]:
                all_content.append(message["content"])
        
        for entry in data["journal_entries"]:
            all_content.append(entry["content"])
        
        combined_content = " ".join(all_content).lower()
        
        # Count theme occurrences
        for theme, keywords in theme_keywords.items():
            for keyword in keywords:
                themes[theme] += len(re.findall(keyword, combined_content))
        
        # Calculate average content length
        if all_content:
            avg_content_length = np.mean([len(content.split()) for content in all_content])
            content_complexity = self._assess_content_complexity(all_content)
        else:
            avg_content_length = 0
            content_complexity = "low"
        
        return {
            "themes": dict(themes),
            "average_content_length": float(avg_content_length),
            "content_complexity": content_complexity,
            "dominant_themes": sorted(themes.items(), key=lambda x: x[1], reverse=True)[:3],
        }

    def _assess_content_complexity(self, content_list: List[str]) -> str:
        """Assess the complexity of content based on various factors"""
        if not content_list:
            return "low"
        
        # Calculate metrics
        avg_sentence_length = np.mean([
            len(content.split('.')) for content in content_list
        ])
        
        unique_words = set()
        total_words = 0
        
        for content in content_list:
            words = content.lower().split()
            unique_words.update(words)
            total_words += len(words)
        
        vocabulary_richness = len(unique_words) / max(1, total_words)
        
        if avg_sentence_length > 5 and vocabulary_richness > 0.7:
            return "high"
        elif avg_sentence_length > 3 and vocabulary_richness > 0.5:
            return "medium"
        else:
            return "low"

    def _analyze_temporal_patterns(self, data: Dict) -> Dict[str, Any]:
        """Analyze temporal patterns in communication"""
        hourly_distribution = defaultdict(int)
        daily_distribution = defaultdict(int)
        
        # Analyze chatbot usage patterns
        for message in data["chatbot_messages"]:
            if message["is_from_user"]:
                dt = timezone.datetime.fromisoformat(message["created_at"].replace('Z', '+00:00'))
                hourly_distribution[dt.hour] += 1
                daily_distribution[dt.strftime('%A')] += 1
        
        # Find peak activity times
        peak_hour = max(hourly_distribution.items(), key=lambda x: x[1])[0] if hourly_distribution else None
        peak_day = max(daily_distribution.items(), key=lambda x: x[1])[0] if daily_distribution else None
        
        return {
            "hourly_distribution": dict(hourly_distribution),
            "daily_distribution": dict(daily_distribution),
            "peak_hour": peak_hour,
            "peak_day": peak_day,
            "activity_consistency": self._calculate_consistency(hourly_distribution),
        }

    def _calculate_consistency(self, distribution: Dict) -> float:
        """Calculate consistency score based on distribution"""
        if not distribution:
            return 0.0
        
        values = list(distribution.values())
        if len(values) < 2:
            return 0.0
        
        # Lower standard deviation indicates higher consistency
        std_dev = np.std(values)
        mean_val = np.mean(values)
        
        # Normalize to 0-1 scale (higher is more consistent)
        consistency = max(0, 1 - (std_dev / max(1, mean_val)))
        return float(consistency)

    def _calculate_engagement_metrics(self, data: Dict) -> Dict[str, Any]:
        """Calculate engagement metrics"""
        user_messages = [msg for msg in data["chatbot_messages"] if msg["is_from_user"]]
        bot_messages = [msg for msg in data["chatbot_messages"] if not msg["is_from_user"]]
        
        # Calculate response rates and engagement
        total_user_messages = len(user_messages)
        total_bot_responses = len(bot_messages)
        
        # Calculate average response time if available
        response_times = [msg.get("response_time") for msg in bot_messages if msg.get("response_time")]
        avg_response_time = np.mean(response_times) if response_times else None
        
        # Calculate engagement score
        engagement_factors = [
            min(1.0, total_user_messages / 30),  # Message frequency
            min(1.0, len(data["journal_entries"]) / 15),  # Journal engagement
            min(1.0, len(data["mood_logs"]) / 20),  # Mood tracking
        ]
        
        engagement_score = np.mean(engagement_factors)
        
        return {
            "total_user_messages": total_user_messages,
            "total_bot_responses": total_bot_responses,
            "response_ratio": total_bot_responses / max(1, total_user_messages),
            "average_response_time": avg_response_time,
            "engagement_score": float(engagement_score),
            "journal_engagement": len(data["journal_entries"]),
            "mood_tracking_engagement": len(data["mood_logs"]),
        }

    def _generate_ai_insights(self, patterns: Dict) -> Dict[str, Any]:
        """Generate AI-powered insights from patterns"""
        try:
            prompt = self._build_analysis_prompt(patterns)
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
            )
            
            if response.status_code == 200:
                result = response.json()
                return self._parse_ai_response(result.get("response", ""))
            else:
                logger.error(f"AI request failed: {response.status_code}")
                return self._create_fallback_insights()
                
        except Exception as e:
            logger.error(f"Error generating AI insights: {str(e)}")
            return self._create_fallback_insights()

    def _build_analysis_prompt(self, patterns: Dict) -> str:
        """Build prompt for AI analysis"""
        return f"""As a communication analysis expert, analyze these communication patterns:

FREQUENCY PATTERNS:
{patterns.get("communication_frequency", {})}

EMOTIONAL PATTERNS:
{patterns.get("emotional_expression", {})}

CONTENT ANALYSIS:
{patterns.get("content_analysis", {})}

TEMPORAL PATTERNS:
{patterns.get("temporal_patterns", {})}

ENGAGEMENT METRICS:
{patterns.get("engagement_metrics", {})}

Provide insights in JSON format:
{{
    "communication_style": "<analytical description>",
    "strengths": ["<list of communication strengths>"],
    "areas_for_improvement": ["<list of areas to improve>"],
    "therapeutic_progress": "<assessment of progress>",
    "recommendations": ["<specific recommendations>"],
    "risk_factors": ["<any concerning patterns>"],
    "overall_assessment": "<overall communication health assessment>"
}}"""

    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """Parse AI response"""
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            parsed = json.loads(response_text)
            
            # Ensure required fields
            required_fields = {
                "communication_style": "analytical",
                "strengths": [],
                "areas_for_improvement": [],
                "therapeutic_progress": "ongoing",
                "recommendations": [],
                "risk_factors": [],
                "overall_assessment": "baseline",
            }
            
            for field, default in required_fields.items():
                if field not in parsed:
                    parsed[field] = default
            
            return parsed
            
        except json.JSONDecodeError:
            logger.error("Failed to parse AI insights response")
            return self._create_fallback_insights()

    def _create_fallback_insights(self) -> Dict[str, Any]:
        """Create fallback insights when AI fails"""
        return {
            "communication_style": "baseline",
            "strengths": ["Active engagement with platform"],
            "areas_for_improvement": ["Continue regular interaction"],
            "therapeutic_progress": "establishing patterns",
            "recommendations": ["Maintain consistent communication"],
            "risk_factors": [],
            "overall_assessment": "developing communication patterns",
        }

    def _analyze_therapist_relationships(self, therapist_user) -> Dict[str, Any]:
        """Analyze therapeutic relationships from therapist perspective"""
        try:
            # Get patients associated with this therapist
            from appointments.models import Appointment
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get recent appointments to find patients
            recent_appointments = Appointment.objects.filter(
                therapist=therapist_user,
                scheduled_time__gte=timezone.now() - timedelta(days=90)
            ).select_related('patient')
            
            patients = list(set([appt.patient for appt in recent_appointments]))
            
            if not patients:
                return {"has_relationships": False, "reason": "no_patients_found"}
            
            relationships = []
            for patient in patients[:10]:  # Limit to 10 most recent patients
                patient_analysis = self._analyze_patient_communication(patient)
                relationships.append({
                    "patient_id": patient.id,
                    "patient_username": patient.username,
                    "communication_analysis": patient_analysis,
                    "appointment_count": recent_appointments.filter(patient=patient).count(),
                })
            
            return {
                "has_relationships": True,
                "user_type": "therapist",
                "total_patients": len(relationships),
                "relationships": relationships,
                "analyzed_at": timezone.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error analyzing therapist relationships: {str(e)}")
            return {"has_relationships": False, "reason": f"error: {str(e)}"}

    def _analyze_patient_relationships(self, patient_user) -> Dict[str, Any]:
        """Analyze therapeutic relationships from patient perspective"""
        try:
            # Get therapists this patient has appointments with
            from appointments.models import Appointment
            
            recent_appointments = Appointment.objects.filter(
                patient=patient_user,
                scheduled_time__gte=timezone.now() - timedelta(days=90)
            ).select_related('therapist')
            
            therapists = list(set([appt.therapist for appt in recent_appointments]))
            
            if not therapists:
                return {"has_relationships": False, "reason": "no_therapists_found"}
            
            relationships = []
            for therapist in therapists:
                therapist_interaction = {
                    "therapist_id": therapist.id,
                    "therapist_username": therapist.username,
                    "appointment_count": recent_appointments.filter(therapist=therapist).count(),
                    "last_appointment": recent_appointments.filter(therapist=therapist).order_by('-scheduled_time').first().scheduled_time.isoformat(),
                }
                relationships.append(therapist_interaction)
            
            # Add patient's own communication analysis
            patient_analysis = self._analyze_patient_communication(patient_user)
            
            return {
                "has_relationships": True,
                "user_type": "patient",
                "total_therapists": len(relationships),
                "relationships": relationships,
                "patient_communication_analysis": patient_analysis,
                "analyzed_at": timezone.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error analyzing patient relationships: {str(e)}")
            return {"has_relationships": False, "reason": f"error: {str(e)}"}

    def _analyze_patient_communication(self, patient) -> Dict[str, Any]:
        """Analyze communication patterns for a specific patient"""
        # Get basic communication metrics
        communication_data = self._collect_communication_data(patient, 30)
        
        if not communication_data["has_data"]:
            return {"engagement_level": "low", "communication_frequency": 0}
        
        # Calculate simple metrics
        total_interactions = communication_data["total_interactions"]
        engagement_level = "high" if total_interactions > 50 else "medium" if total_interactions > 20 else "low"
        
        return {
            "engagement_level": engagement_level,
            "communication_frequency": total_interactions / 30,
            "chatbot_usage": len(communication_data["chatbot_messages"]),
            "journal_activity": len(communication_data["journal_entries"]),
            "mood_tracking": len(communication_data["mood_logs"]),
        }

    def _create_no_data_response(self) -> Dict[str, Any]:
        """Create response when no communication data is found"""
        return {
            "has_data": False,
            "message": "No communication data found for analysis",
            "suggestions": [
                "Start using the chatbot to build communication history",
                "Create journal entries to track thoughts and feelings",
                "Log mood entries regularly",
            ],
            "analyzed_at": timezone.now().isoformat(),
        }

    def _create_no_relationship_response(self) -> Dict[str, Any]:
        """Create response when no therapeutic relationships are found"""
        return {
            "has_relationships": False,
            "message": "No therapeutic relationship data found",
            "suggestions": [
                "Schedule an appointment with a therapist",
                "Start building therapeutic communication through regular platform use",
            ],
            "analyzed_at": timezone.now().isoformat(),
        }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            "error": True,
            "message": f"Error analyzing communication: {error_message}",
            "analyzed_at": timezone.now().isoformat(),
        }


# Create singleton instance
communication_analysis_service = CommunicationAnalysisService()
