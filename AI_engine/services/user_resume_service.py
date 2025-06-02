import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
import json

from .ai_analysis import ai_service
from .data_interface import ai_data_interface
from datawarehouse.models import (
    UserDataSnapshot, 
    MoodTrendAnalysis,
    CommunicationMetrics,
    FeatureUsageMetrics
)

User = get_user_model()
logger = logging.getLogger(__name__)


class UserResumeService:
    """AI-driven service for generating comprehensive user resumes for therapists"""
    
    def __init__(self):
        self.ai_service = ai_service
        self.data_interface = ai_data_interface
    
    def generate_user_resume(self, user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Generate a comprehensive AI-driven user resume with 4 analytics cards
        plus an AI summary for therapists
        """
        try:
            user = User.objects.get(id=user_id)
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=period_days)
            
            # Get AI-ready dataset for comprehensive analysis
            dataset = self.data_interface.get_ai_ready_dataset(user_id, period_days)
            
            # Generate the 4 analytics cards
            card_1_mental_health = self._generate_mental_health_card(user, dataset, period_days)
            card_2_behavioral = self._generate_behavioral_patterns_card(user, dataset, period_days)
            card_3_social_engagement = self._generate_social_engagement_card(user, dataset, period_days)
            card_4_progress_tracking = self._generate_progress_tracking_card(user, dataset, period_days)
            
            # Generate AI-driven therapist guidance
            ai_therapist_summary = self._generate_ai_therapist_summary(user, dataset, {
                'mental_health': card_1_mental_health,
                'behavioral': card_2_behavioral,
                'social': card_3_social_engagement,
                'progress': card_4_progress_tracking
            })
            
            return {
                'user_id': user_id,
                'user_info': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': user.user_type,
                    'date_joined': user.date_joined.isoformat()
                },
                'period_info': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'period_days': period_days
                },
                'analytics_cards': {
                    'mental_health_overview': card_1_mental_health,
                    'behavioral_patterns': card_2_behavioral,
                    'social_engagement': card_3_social_engagement,
                    'progress_tracking': card_4_progress_tracking
                },
                'ai_therapist_summary': ai_therapist_summary,
                'data_quality': dataset.get('quality_metrics', {}),
                'last_updated': timezone.now().isoformat()
            }
            
        except User.DoesNotExist:
            logger.error(f"User with ID {user_id} not found")
            return {'error': f'User with ID {user_id} not found'}
        except Exception as e:
            logger.error(f"Error generating user resume for user {user_id}: {str(e)}")
            return {'error': f'Failed to generate resume: {str(e)}'}
    
    def _generate_mental_health_card(self, user, dataset: Dict, period_days: int) -> Dict[str, Any]:
        """Generate Card 1: Mental Health Overview"""
        try:
            mood_analytics = dataset.get('mood_analytics', {})
            journal_analytics = dataset.get('journal_analytics', {})
            
            # Get latest mood trend analysis
            latest_mood_trend = MoodTrendAnalysis.objects.filter(
                user=user,
                analysis_type='weekly'
            ).order_by('-created_at').first()
            
            # Calculate risk indicators
            risk_indicators = []
            risk_level = 'low'
            
            if mood_analytics.get('average_mood', 5) < 4:
                risk_indicators.append('Low average mood score')
                risk_level = 'moderate'
            
            if mood_analytics.get('mood_volatility', 0) > 2:
                risk_indicators.append('High mood volatility')
                risk_level = 'moderate'
            
            if journal_analytics.get('negative_sentiment_ratio', 0) > 0.6:
                risk_indicators.append('Predominantly negative journal sentiment')
                risk_level = 'high'
            
            # Dominant emotions from mood tracking
            dominant_emotions = mood_analytics.get('dominant_emotions', ['neutral'])
            
            # Key mental health themes from journal analysis
            mental_health_themes = journal_analytics.get('key_themes', [])
            
            return {
                'card_title': 'Mental Health Overview',
                'summary_metrics': {
                    'average_mood_score': round(mood_analytics.get('average_mood', 5), 2),
                    'mood_trend': mood_analytics.get('mood_trend', 'stable'),
                    'mood_volatility': round(mood_analytics.get('mood_volatility', 0), 2),
                    'risk_level': risk_level
                },
                'dominant_emotions': dominant_emotions[:5],  # Top 5 emotions
                'mental_health_themes': mental_health_themes[:5],  # Top 5 themes
                'risk_indicators': risk_indicators,
                'journal_sentiment_trend': journal_analytics.get('sentiment_trend', 'neutral'),
                'mood_consistency_score': latest_mood_trend.consistency_score if latest_mood_trend else 0,
                'needs_attention': len(risk_indicators) > 2 or risk_level == 'high',
                'data_points': {
                    'mood_entries_count': len(dataset.get('mood_data', [])),
                    'journal_entries_count': len(dataset.get('journal_data', []))
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating mental health card: {str(e)}")
            return {'card_title': 'Mental Health Overview', 'error': str(e)}
    
    def _generate_behavioral_patterns_card(self, user, dataset: Dict, period_days: int) -> Dict[str, Any]:
        """Generate Card 2: Behavioral Patterns"""
        try:
            behavioral_analytics = dataset.get('behavioral_analytics', {})
            
            # Get feature usage metrics
            feature_metrics = FeatureUsageMetrics.objects.filter(
                user=user,
                date__gte=timezone.now().date() - timedelta(days=period_days)
            ).aggregate(
                avg_sessions=Avg('session_count'),
                total_time=Avg('total_time_spent_minutes'),
                avg_engagement=Avg('engagement_score')
            )
            
            # Activity patterns from behavioral analytics
            activity_patterns = behavioral_analytics.get('activity_patterns', {})
            engagement_metrics = behavioral_analytics.get('engagement_metrics', {})
            
            # Calculate behavioral insights
            app_usage_trend = 'stable'
            if feature_metrics['avg_sessions'] and feature_metrics['avg_sessions'] > 3:
                app_usage_trend = 'increasing'
            elif feature_metrics['avg_sessions'] and feature_metrics['avg_sessions'] < 1:
                app_usage_trend = 'decreasing'
            
            # Identify behavioral patterns
            behavioral_insights = []
            if engagement_metrics.get('daily_consistency', 0) > 0.7:
                behavioral_insights.append('High daily engagement consistency')
            if activity_patterns.get('peak_usage_time'):
                behavioral_insights.append(f"Most active during {activity_patterns['peak_usage_time']}")
            if engagement_metrics.get('feature_diversity', 0) > 0.6:
                behavioral_insights.append('Uses diverse app features')
            
            return {
                'card_title': 'Behavioral Patterns',
                'usage_metrics': {
                    'avg_daily_sessions': round(feature_metrics['avg_sessions'] or 0, 1),
                    'avg_session_duration': round(feature_metrics['total_time'] or 0, 1),
                    'engagement_score': round(feature_metrics['avg_engagement'] or 0, 2),
                    'usage_trend': app_usage_trend
                },
                'activity_patterns': {
                    'peak_usage_time': activity_patterns.get('peak_usage_time', 'Unknown'),
                    'most_used_features': activity_patterns.get('most_used_features', [])[:3],
                    'interaction_frequency': activity_patterns.get('interaction_frequency', 'moderate')
                },
                'behavioral_insights': behavioral_insights,
                'engagement_level': self._calculate_engagement_level(feature_metrics['avg_engagement'] or 0),
                'consistency_score': engagement_metrics.get('daily_consistency', 0),
                'feature_adoption_rate': engagement_metrics.get('feature_diversity', 0)
            }
            
        except Exception as e:
            logger.error(f"Error generating behavioral patterns card: {str(e)}")
            return {'card_title': 'Behavioral Patterns', 'error': str(e)}
    
    def _generate_social_engagement_card(self, user, dataset: Dict, period_days: int) -> Dict[str, Any]:
        """Generate Card 3: Social Engagement & Communication"""
        try:
            social_analytics = dataset.get('social_analytics', {})
            communication_analytics = dataset.get('communication_analytics', {})
            
            # Get communication metrics
            comm_metrics = CommunicationMetrics.objects.filter(
                user=user,
                period_start__gte=timezone.now().date() - timedelta(days=period_days)
            ).order_by('-period_start').first()
            
            # Social engagement indicators
            social_engagement_level = social_analytics.get('social_engagement', 'moderate')
            support_network_quality = social_analytics.get('support_network', 'unknown')
            
            # Communication patterns
            communication_sentiment = communication_analytics.get('sentiment_trend', 'neutral')
            interaction_frequency = communication_analytics.get('interaction_frequency', 'moderate')
            
            # Calculate social health score
            social_health_score = self._calculate_social_health_score(
                social_engagement_level,
                support_network_quality,
                communication_sentiment,
                comm_metrics
            )
            
            # Social insights
            social_insights = []
            if social_engagement_level == 'high':
                social_insights.append('Maintains active social connections')
            elif social_engagement_level == 'low':
                social_insights.append('May benefit from increased social interaction')
            
            if communication_sentiment == 'positive':
                social_insights.append('Positive communication patterns')
            elif communication_sentiment == 'negative':
                social_insights.append('Communication shows concerning patterns')
            
            return {
                'card_title': 'Social Engagement & Communication',
                'social_metrics': {
                    'social_engagement_level': social_engagement_level,
                    'support_network_quality': support_network_quality,
                    'social_health_score': social_health_score,
                    'interaction_frequency': interaction_frequency
                },
                'communication_patterns': {
                    'sentiment_trend': communication_sentiment,
                    'messages_sent': comm_metrics.messages_sent if comm_metrics else 0,
                    'messages_received': comm_metrics.messages_received if comm_metrics else 0,
                    'avg_response_time': comm_metrics.avg_response_time_minutes if comm_metrics else 0
                },
                'social_insights': social_insights,
                'interaction_quality': social_analytics.get('interaction_patterns', 'healthy'),
                'community_involvement': social_analytics.get('community_engagement', 'moderate'),
                'support_seeking_behavior': self._analyze_support_seeking(dataset)
            }
            
        except Exception as e:
            logger.error(f"Error generating social engagement card: {str(e)}")
            return {'card_title': 'Social Engagement & Communication', 'error': str(e)}
    
    def _generate_progress_tracking_card(self, user, dataset: Dict, period_days: int) -> Dict[str, Any]:
        """Generate Card 4: Progress Tracking & Recommendations"""
        try:
            # Get latest user data snapshot for progress comparison
            latest_snapshot = UserDataSnapshot.objects.filter(user=user).order_by('-snapshot_date').first()
            previous_snapshot = UserDataSnapshot.objects.filter(
                user=user,
                snapshot_date__lt=latest_snapshot.snapshot_date if latest_snapshot else timezone.now().date()
            ).order_by('-snapshot_date').first() if latest_snapshot else None
            
            # Calculate progress indicators
            progress_indicators = {}
            if latest_snapshot and previous_snapshot:
                progress_indicators = {
                    'mood_improvement': latest_snapshot.avg_mood_score - previous_snapshot.avg_mood_score,
                    'engagement_change': latest_snapshot.social_engagement_score - previous_snapshot.social_engagement_score,
                    'data_quality_improvement': latest_snapshot.data_quality_score - previous_snapshot.data_quality_score
                }
            
            # Get recent AI recommendations
            recent_recommendations = self._get_recent_recommendations(user)
            
            # Therapy readiness assessment
            therapy_readiness = self._assess_therapy_readiness(user, dataset, latest_snapshot)
            
            # Progress trends
            progress_trends = []
            if progress_indicators.get('mood_improvement', 0) > 0.5:
                progress_trends.append('Mood showing positive improvement')
            elif progress_indicators.get('mood_improvement', 0) < -0.5:
                progress_trends.append('Mood declining - needs attention')
            
            if progress_indicators.get('engagement_change', 0) > 0.1:
                progress_trends.append('Increased social engagement')
            
            # Current intervention priorities
            intervention_priorities = self._identify_intervention_priorities(dataset, latest_snapshot)
            
            return {
                'card_title': 'Progress Tracking & Recommendations',
                'progress_metrics': {
                    'mood_trend_direction': 'improving' if progress_indicators.get('mood_improvement', 0) > 0 else 'stable',
                    'overall_progress_score': self._calculate_overall_progress_score(progress_indicators),
                    'data_completeness': dataset.get('quality_metrics', {}).get('completeness', 0),
                    'therapy_readiness_score': therapy_readiness['score']
                },
                'progress_indicators': progress_indicators,
                'progress_trends': progress_trends,
                'recent_ai_recommendations': recent_recommendations[:3],  # Top 3 recommendations
                'intervention_priorities': intervention_priorities,
                'therapy_readiness': therapy_readiness,
                'next_assessment_due': (timezone.now() + timedelta(days=7)).date().isoformat(),
                'monitoring_alerts': self._generate_monitoring_alerts(dataset, latest_snapshot)
            }
            
        except Exception as e:
            logger.error(f"Error generating progress tracking card: {str(e)}")
            return {'card_title': 'Progress Tracking & Recommendations', 'error': str(e)}
    
    def _generate_ai_therapist_summary(self, user, dataset: Dict, cards_data: Dict) -> Dict[str, Any]:
        """Generate AI-driven summary and guidance for therapists"""
        try:
            # Create comprehensive prompt for therapist guidance
            prompt = self._create_therapist_guidance_prompt(user, dataset, cards_data)
            
            # Get AI analysis
            ai_response = self.ai_service.generate_text(prompt)
            
            # Parse AI response into structured guidance
            therapist_guidance = self._parse_therapist_guidance(ai_response.get('text', ''))
            
            # Add clinical insights
            clinical_insights = self._generate_clinical_insights(dataset, cards_data)
            
            return {
                'ai_summary': therapist_guidance.get('summary', 'AI analysis not available'),
                'key_concerns': therapist_guidance.get('concerns', []),
                'therapeutic_recommendations': therapist_guidance.get('recommendations', []),
                'session_focus_areas': therapist_guidance.get('focus_areas', []),
                'clinical_insights': clinical_insights,
                'risk_assessment': therapist_guidance.get('risk_assessment', 'low'),
                'intervention_suggestions': therapist_guidance.get('interventions', []),
                'progress_observations': therapist_guidance.get('progress', ''),
                'therapist_notes': therapist_guidance.get('notes', ''),
                'generated_at': timezone.now().isoformat(),
                'ai_confidence_score': therapist_guidance.get('confidence', 0.7)
            }
            
        except Exception as e:
            logger.error(f"Error generating AI therapist summary: {str(e)}")
            return {
                'ai_summary': 'Error generating AI summary',
                'error': str(e),
                'generated_at': timezone.now().isoformat()
            }
    
    def _create_therapist_guidance_prompt(self, user, dataset: Dict, cards_data: Dict) -> str:
        """Create prompt for AI therapist guidance"""
        prompt = f"""
        As a clinical AI assistant, analyze this comprehensive patient data and provide therapeutic guidance:

        PATIENT OVERVIEW:
        - User: {user.username} (ID: {user.id})
        - User Type: {user.user_type}
        - Data Quality: {dataset.get('quality_metrics', {}).get('overall_quality', 0):.2f}/1.0

        ANALYTICS SUMMARY:
        1. Mental Health: {cards_data['mental_health']}
        
        2. Behavioral Patterns: {cards_data['behavioral']}
        
        3. Social Engagement: {cards_data['social']}
        
        4. Progress Tracking: {cards_data['progress']}

        PROVIDE THERAPEUTIC GUIDANCE IN THIS FORMAT:
        
        SUMMARY: [2-3 sentence overall assessment]
        
        KEY_CONCERNS: [List 3-5 primary areas needing attention]
        
        THERAPEUTIC_RECOMMENDATIONS: [Specific evidence-based interventions]
        
        FOCUS_AREAS: [Suggested topics for therapy sessions]
        
        RISK_ASSESSMENT: [low/moderate/high with rationale]
        
        INTERVENTIONS: [Immediate actions or referrals needed]
        
        PROGRESS: [Notable improvements or deteriorations]
        
        NOTES: [Additional clinical observations]
        
        Focus on actionable, evidence-based recommendations that would help a therapist prepare for and conduct effective sessions.
        """
        return prompt
    
    def _parse_therapist_guidance(self, ai_text: str) -> Dict[str, Any]:
        """Parse AI response into structured therapist guidance"""
        try:
            import re
            
            guidance = {
                'summary': '',
                'concerns': [],
                'recommendations': [],
                'focus_areas': [],
                'risk_assessment': 'moderate',
                'interventions': [],
                'progress': '',
                'notes': '',
                'confidence': 0.7
            }
            
            # Extract summary
            summary_match = re.search(r'SUMMARY:\s*(.*?)(?=KEY_CONCERNS:|$)', ai_text, re.DOTALL | re.IGNORECASE)
            if summary_match:
                guidance['summary'] = summary_match.group(1).strip()
            
            # Extract key concerns
            concerns_match = re.search(r'KEY_CONCERNS:\s*(.*?)(?=THERAPEUTIC_RECOMMENDATIONS:|$)', ai_text, re.DOTALL | re.IGNORECASE)
            if concerns_match:
                concerns_text = concerns_match.group(1).strip()
                guidance['concerns'] = [c.strip('- ').strip() for c in concerns_text.split('\n') if c.strip()]
            
            # Extract recommendations
            recommendations_match = re.search(r'THERAPEUTIC_RECOMMENDATIONS:\s*(.*?)(?=FOCUS_AREAS:|$)', ai_text, re.DOTALL | re.IGNORECASE)
            if recommendations_match:
                recommendations_text = recommendations_match.group(1).strip()
                guidance['recommendations'] = [r.strip('- ').strip() for r in recommendations_text.split('\n') if r.strip()]
            
            # Extract focus areas
            focus_match = re.search(r'FOCUS_AREAS:\s*(.*?)(?=RISK_ASSESSMENT:|$)', ai_text, re.DOTALL | re.IGNORECASE)
            if focus_match:
                focus_text = focus_match.group(1).strip()
                guidance['focus_areas'] = [f.strip('- ').strip() for f in focus_text.split('\n') if f.strip()]
            
            # Extract risk assessment
            risk_match = re.search(r'RISK_ASSESSMENT:\s*(.*?)(?=INTERVENTIONS:|$)', ai_text, re.DOTALL | re.IGNORECASE)
            if risk_match:
                risk_text = risk_match.group(1).strip().lower()
                if 'high' in risk_text:
                    guidance['risk_assessment'] = 'high'
                elif 'low' in risk_text:
                    guidance['risk_assessment'] = 'low'
                else:
                    guidance['risk_assessment'] = 'moderate'
            
            return guidance
            
        except Exception as e:
            logger.error(f"Error parsing therapist guidance: {str(e)}")
            return {'summary': 'Error parsing AI guidance', 'error': str(e)}
    
    # Helper methods
    def _calculate_engagement_level(self, engagement_score: float) -> str:
        """Calculate engagement level from score"""
        if engagement_score >= 0.7:
            return 'high'
        elif engagement_score >= 0.4:
            return 'moderate'
        else:
            return 'low'
    
    def _calculate_social_health_score(self, engagement, support_network, sentiment, comm_metrics) -> float:
        """Calculate overall social health score"""
        score = 0.5  # Base score
        
        if engagement == 'high':
            score += 0.2
        elif engagement == 'low':
            score -= 0.2
        
        if support_network == 'strong':
            score += 0.2
        elif support_network == 'weak':
            score -= 0.2
        
        if sentiment == 'positive':
            score += 0.1
        elif sentiment == 'negative':
            score -= 0.1
        
        return max(0, min(1, score))
    
    def _analyze_support_seeking(self, dataset: Dict) -> str:
        """Analyze support seeking behavior"""
        communication_data = dataset.get('communication_analytics', {})
        
        if communication_data.get('help_seeking_indicators', 0) > 0.6:
            return 'actively_seeking'
        elif communication_data.get('help_seeking_indicators', 0) < 0.3:
            return 'reluctant'
        else:
            return 'moderate'
    
    def _get_recent_recommendations(self, user) -> List[Dict]:
        """Get recent AI recommendations for the user"""
        try:
            from ..models import TherapyRecommendation
            recent_recs = TherapyRecommendation.objects.filter(
                user=user
            ).order_by('-created_at')[:5]
            
            return [
                {
                    'type': rec.recommendation_type,
                    'recommendation': rec.recommendation_data.get('description', ''),
                    'priority': rec.recommendation_data.get('priority', 'medium'),
                    'created_at': rec.created_at.isoformat()
                }
                for rec in recent_recs
            ]
        except Exception:
            return []
    
    def _assess_therapy_readiness(self, user, dataset: Dict, snapshot) -> Dict[str, Any]:
        """Assess user's readiness for therapy"""
        readiness_score = 0.5  # Base score
        
        # Factor in engagement
        if snapshot and snapshot.social_engagement_score > 0.6:
            readiness_score += 0.2
        
        # Factor in data quality
        if dataset.get('quality_metrics', {}).get('completeness', 0) > 0.7:
            readiness_score += 0.1
        
        # Factor in mood stability
        mood_analytics = dataset.get('mood_analytics', {})
        if mood_analytics.get('mood_volatility', 2) < 1.5:
            readiness_score += 0.2
        
        return {
            'score': min(1.0, readiness_score),
            'level': 'high' if readiness_score > 0.7 else 'moderate' if readiness_score > 0.4 else 'low',
            'factors': ['engagement_level', 'data_quality', 'mood_stability']
        }
    
    def _identify_intervention_priorities(self, dataset: Dict, snapshot) -> List[str]:
        """Identify top intervention priorities"""
        priorities = []
        
        mood_analytics = dataset.get('mood_analytics', {})
        if mood_analytics.get('average_mood', 5) < 4:
            priorities.append('Mood stabilization')
        
        if mood_analytics.get('mood_volatility', 0) > 2:
            priorities.append('Emotional regulation')
        
        social_analytics = dataset.get('social_analytics', {})
        if social_analytics.get('social_engagement', 'moderate') == 'low':
            priorities.append('Social connection building')
        
        if snapshot and snapshot.needs_attention:
            priorities.append('Crisis intervention assessment')
        
        return priorities[:3]  # Top 3 priorities
    
    def _calculate_overall_progress_score(self, indicators: Dict) -> float:
        """Calculate overall progress score"""
        if not indicators:
            return 0.5
        
        score = 0.5
        score += indicators.get('mood_improvement', 0) * 0.3
        score += indicators.get('engagement_change', 0) * 0.2
        
        return max(0, min(1, score))
    
    def _generate_monitoring_alerts(self, dataset: Dict, snapshot) -> List[str]:
        """Generate monitoring alerts for therapists"""
        alerts = []
        
        if snapshot and snapshot.needs_attention:
            alerts.append('High risk indicators detected')
        
        mood_analytics = dataset.get('mood_analytics', {})
        if mood_analytics.get('average_mood', 5) < 3:
            alerts.append('Severely low mood scores')
        
        if dataset.get('quality_metrics', {}).get('completeness', 1) < 0.3:
            alerts.append('Insufficient data for accurate assessment')
        
        return alerts
    
    def _generate_clinical_insights(self, dataset: Dict, cards_data: Dict) -> List[str]:
        """Generate clinical insights from data analysis"""
        insights = []
        
        # Mood-related insights
        mental_health = cards_data.get('mental_health', {})
        if mental_health.get('needs_attention'):
            insights.append('Mental health status requires immediate attention')
        
        # Behavioral insights
        behavioral = cards_data.get('behavioral', {})
        usage_trend = behavioral.get('usage_metrics', {}).get('usage_trend', 'stable')
        if usage_trend == 'decreasing':
            insights.append('Declining app engagement may indicate decreased motivation')
        
        # Social insights
        social = cards_data.get('social', {})
        social_health = social.get('social_metrics', {}).get('social_health_score', 0.5)
        if social_health < 0.4:
            insights.append('Social isolation patterns detected - consider group therapy')
        
        return insights


# Create singleton instance
user_resume_service = UserResumeService()
