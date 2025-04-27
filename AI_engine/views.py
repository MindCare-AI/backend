import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.core.cache import cache

from .models import UserAnalysis, TherapyRecommendation, AIInsight
from .serializers import (
    UserAnalysisSerializer,
    TherapyRecommendationSerializer,
    AIInsightSerializer
)
from .services import AIAnalysisService, ai_service
from AI_engine.services.predictive_service import predictive_service
from AI_engine.services.therapy_analysis import therapy_analysis

logger = logging.getLogger(__name__)

class AIAnalysisViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserAnalysisSerializer
    
    def get_queryset(self):
        return UserAnalysis.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def analyze_data(self, request):
        """Trigger a new analysis of user's data"""
        try:
            service = AIAnalysisService()
            date_range = request.data.get('date_range', 30)
            analysis = service.analyze_user_data(request.user, date_range)
            
            if analysis:
                serializer = self.get_serializer(analysis)
                return Response(serializer.data)
            return Response(
                {"error": "Could not generate analysis"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get the latest analysis"""
        analysis = self.get_queryset().first()
        if analysis:
            serializer = self.get_serializer(analysis)
            return Response(serializer.data)
        return Response(
            {"error": "No analysis found"},
            status=status.HTTP_404_NOT_FOUND
        )

class AIInsightViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AIInsightSerializer
    
    def get_queryset(self):
        return AIInsight.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_addressed(self, request, pk=None):
        """Mark an insight as addressed"""
        insight = self.get_object()
        insight.is_addressed = True
        insight.save()
        serializer = self.get_serializer(insight)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def chatbot_context(self, request):
        """Get AI insights for chatbot context"""
        try:
            cache_key = f'chatbot_context_{request.user.id}'
            context = cache.get(cache_key)
            
            if not context:
                # Get fresh analysis
                mood_prediction = predictive_service.predict_mood_decline(request.user)
                journal_analysis = predictive_service.analyze_journal_patterns(request.user)
                
                if hasattr(request.user, 'patient_profile'):
                    therapy_prediction = therapy_analysis.recommend_session_focus(request.user)
                else:
                    therapy_prediction = None
                
                context = {
                    'mood_prediction': mood_prediction,
                    'journal_analysis': journal_analysis,
                    'therapy_insights': therapy_prediction,
                    'generated_at': timezone.now().isoformat()
                }
                
                # Cache for 15 minutes
                cache.set(cache_key, context, timeout=900)
            
            return Response(context)
            
        except Exception as e:
            logger.error(f"Error getting chatbot context: {str(e)}")
            return Response(
                {'error': 'Could not retrieve AI context'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def analyze_user(self, request):
        """Trigger a new analysis for the user"""
        try:
            analysis = ai_service.analyze_user_data(request.user)
            if analysis:
                return Response({
                    'status': 'success',
                    'analysis': {
                        'mood_score': analysis.mood_score,
                        'sentiment_score': analysis.sentiment_score,
                        'dominant_emotions': analysis.dominant_emotions,
                        'topics_of_concern': analysis.topics_of_concern,
                        'suggested_activities': analysis.suggested_activities
                    }
                })
            return Response(
                {'error': 'Could not generate analysis'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Error in analyze_user: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TherapyRecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TherapyRecommendationSerializer
    
    def get_queryset(self):
        return TherapyRecommendation.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def rate_effectiveness(self, request, pk=None):
        """Rate the effectiveness of a recommendation"""
        recommendation = self.get_object()
        rating = request.data.get('rating')
        if rating is not None and 1 <= rating <= 5:
            recommendation.effectiveness_rating = rating
            recommendation.save()
            serializer = self.get_serializer(recommendation)
            return Response(serializer.data)
        return Response(
            {"error": "Invalid rating. Must be between 1 and 5"},
            status=status.HTTP_400_BAD_REQUEST
        )
