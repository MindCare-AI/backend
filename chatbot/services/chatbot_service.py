"""Chatbot service using Google's Gemini API"""
import logging
from django.conf import settings
from typing import Dict, Any, List, Tuple
from django.utils import timezone
from datetime import timedelta
from AI_engine.services import ai_service
from journal.models import JournalEntry
from mood.models import MoodLog
from ..exceptions import ChatbotConfigError, ChatbotAPIError

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot interactions using Gemini"""

    def __init__(self):
        self.timeout = settings.CHATBOT_SETTINGS["RESPONSE_TIMEOUT"]
        self.max_retries = settings.CHATBOT_SETTINGS["MAX_RETRIES"]
        self.history_limit = settings.CHATBOT_SETTINGS["MAX_HISTORY_MESSAGES"]
        self.journal_limit = getattr(settings, "CHATBOT_JOURNAL_LIMIT", 5)
        self.mood_limit = getattr(settings, "CHATBOT_MOOD_LIMIT", 10)
        self.lookback_days = getattr(settings, "CHATBOT_LOOKBACK_DAYS", 30)

    def get_response(
        self, user, message: str, conversation_history: list = None
    ) -> Dict[str, any]:
        """Get response from Gemini with user context and AI analysis"""
        try:
            # Get user's journal entries and mood data
            user_data = self._get_user_data(user)
            
            # Build prompt with context including journal and mood data
            prompt = self._build_prompt(message, conversation_history, user_data)

            # Get response from AI service
            try:
                response = ai_service.generate_text(prompt)
                return {
                    "content": response["text"],
                    "metadata": response.get("metadata", {})
                }
            except Exception as e:
                raise ChatbotAPIError(f"Gemini API error: {str(e)}")

        except Exception as e:
            logger.error(f"Error getting chatbot response: {str(e)}")
            return self._error_response(str(e))

    def _get_user_data(self, user) -> Dict[str, Any]:
        """Retrieve user's journal entries and mood logs"""
        try:
            # Define the lookback period
            end_date = timezone.now()
            start_date = end_date - timedelta(days=self.lookback_days)
            
            # Get recent journal entries
            journal_entries = JournalEntry.objects.filter(
                user=user, 
                created_at__range=(start_date, end_date)
            ).order_by('-created_at')[:self.journal_limit]
            
            # Get recent mood logs
            mood_logs = MoodLog.objects.filter(
                user=user,
                logged_at__range=(start_date, end_date)
            ).order_by('-logged_at')[:self.mood_limit]
            
            # Format the data
            journal_data = []
            for entry in journal_entries:
                journal_data.append({
                    'date': entry.created_at.strftime('%Y-%m-%d'),
                    'content': entry.content,
                    'mood': entry.mood if hasattr(entry, 'mood') else None,
                    'activities': entry.activities if hasattr(entry, 'activities') else None
                })
                
            mood_data = []
            for log in mood_logs:
                mood_data.append({
                    'date': log.logged_at.strftime('%Y-%m-%d'),
                    'mood_rating': log.mood_rating,
                    'activities': log.activities if hasattr(log, 'activities') else None,
                    'notes': log.notes if hasattr(log, 'notes') else None
                })
            
            # Get AI analysis if available
            analysis = None
            try:
                from AI_engine.models import UserAnalysis
                latest_analysis = UserAnalysis.objects.filter(user=user).order_by('-analysis_date').first()
                if latest_analysis:
                    analysis = {
                        'mood_score': latest_analysis.mood_score,
                        'sentiment_score': latest_analysis.sentiment_score,
                        'dominant_emotions': latest_analysis.dominant_emotions,
                        'topics_of_concern': latest_analysis.topics_of_concern,
                        'suggested_activities': latest_analysis.suggested_activities,
                    }
            except Exception as e:
                logger.warning(f"Could not retrieve AI analysis: {str(e)}")
                
            return {
                'journal_entries': journal_data,
                'mood_logs': mood_data,
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Error retrieving user data: {str(e)}")
            return {'error': str(e)}

    def _build_prompt(self, message: str, history: list = None, user_data: Dict = None) -> str:
        """Build prompt string with message, history and user data"""
        prompt_parts = []
        
        # Add system context with user data if available
        prompt_parts.append("You are MindCare AI, a therapeutic chatbot assistant.")
        
        # Add user's journal and mood data if available
        if user_data and not user_data.get('error'):
            prompt_parts.append("\nUser's recent journal entries and mood data:")
            
            # Add journal entries
            if user_data.get('journal_entries'):
                prompt_parts.append("\nJournal entries:")
                for i, entry in enumerate(user_data['journal_entries']):
                    prompt_parts.append(f"Entry {i+1} ({entry['date']}): {entry['content']}")
            
            # Add mood logs
            if user_data.get('mood_logs'):
                prompt_parts.append("\nMood logs:")
                for i, log in enumerate(user_data['mood_logs']):
                    mood_info = f"Log {i+1} ({log['date']}): Rating {log['mood_rating']}/10"
                    if log.get('notes'):
                        mood_info += f", Notes: {log['notes']}"
                    prompt_parts.append(mood_info)
            
            # Add AI analysis if available
            if user_data.get('analysis'):
                analysis = user_data['analysis']
                prompt_parts.append("\nAI analysis of user's data:")
                prompt_parts.append(f"Mood score: {analysis.get('mood_score', 'Unknown')}")
                prompt_parts.append(f"Sentiment: {analysis.get('sentiment_score', 'Unknown')}")
                prompt_parts.append(f"Dominant emotions: {', '.join(analysis.get('dominant_emotions', ['Unknown']))}")
                prompt_parts.append(f"Topics of concern: {', '.join(analysis.get('topics_of_concern', ['Unknown']))}")
                
            prompt_parts.append("\nInstructions for response:")
            prompt_parts.append("- Refer to the user's journal entries and mood data when relevant")
            prompt_parts.append("- Provide empathetic and personalized guidance based on their data")
            prompt_parts.append("- Don't mention specific details unless the user brings them up first")
            prompt_parts.append("- Maintain a supportive and non-judgmental tone")
        
        # Add conversation history if provided
        if history:
            prompt_parts.append("\nConversation history:")
            for msg in history[-self.history_limit:]:
                role = "Bot" if msg.get("is_bot") else "User"
                prompt_parts.append(f"{role}: {msg.get('content')}")
        
        # Add current message
        prompt_parts.append(f"\nUser: {message}")
        prompt_parts.append("\nAssistant:")
        
        return "\n".join(prompt_parts)

    def _error_response(self, message: str) -> Dict[str, any]:
        """Generate error response"""
        return {
            "content": "I apologize, but I'm having trouble processing your message right now. Please try again in a moment.",
            "metadata": {"error": message}
        }


# Create singleton instance
chatbot_service = ChatbotService()