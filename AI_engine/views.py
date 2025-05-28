# AI_engine/views.py
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta

from .models import (
    UserAnalysis,
    AIInsight,
    TherapyRecommendation,
    CommunicationPatternAnalysis,
)
from .serializers import (
    UserAnalysisSerializer,
    AIInsightSerializer,
    TherapyRecommendationSerializer,
    CommunicationPatternAnalysisSerializer,
)
from .services.ai_analysis import ai_service
from .services.communication_analysis import communication_analysis_service

logger = logging.getLogger(__name__)


class AIAnalysisViewSet(viewsets.ModelViewSet):
    """ViewSet for AI analysis of user data"""
    serializer_class = UserAnalysisSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserAnalysis.objects.filter(user=self.request.user)


class AIInsightViewSet(viewsets.ViewSet):
    """ViewSet for AI insights"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List AI insights for the current user"""
        try:
            insights = AIInsight.objects.filter(user=request.user).order_by('-created_at')[:10]
            serializer = AIInsightSerializer(insights, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing insights: {str(e)}")
            return Response(
                {"error": "Failed to retrieve insights"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, pk=None):
        """Retrieve a specific insight"""
        try:
            insight = AIInsight.objects.get(pk=pk, user=request.user)
            serializer = AIInsightSerializer(insight)
            return Response(serializer.data)
        except AIInsight.DoesNotExist:
            return Response(
                {"error": "Insight not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def mark_addressed(self, request, pk=None):
        """Mark an insight as addressed"""
        try:
            insight = AIInsight.objects.get(pk=pk, user=request.user)
            insight.is_addressed = True
            insight.save()
            return Response({"message": "Insight marked as addressed"})
        except AIInsight.DoesNotExist:
            return Response(
                {"error": "Insight not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def chatbot_context(self, request):
        """Get insights for chatbot context"""
        try:
            recent_insights = AIInsight.objects.filter(
                user=request.user,
                created_at__gte=timezone.now() - timedelta(days=7),
                is_addressed=False
            ).order_by('-created_at')[:5]
            
            context_data = [
                {
                    "type": insight.insight_type,
                    "data": insight.insight_data,
                    "priority": insight.priority,
                    "created_at": insight.created_at.isoformat(),
                }
                for insight in recent_insights
            ]
            
            return Response({"insights": context_data})
        except Exception as e:
            logger.error(f"Error getting chatbot context: {str(e)}")
            return Response(
                {"error": "Failed to retrieve context"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def analyze_user(self, request):
        """Trigger AI analysis for the current user"""
        try:
            # Get days parameter from request body, default to 7
            days = request.data.get('days', 7)
            
            # Validate days parameter
            try:
                days = int(days)
                if days < 1 or days > 90:
                    return Response(
                        {"error": "Days must be between 1 and 90"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return Response(
                    {"error": "Days must be a valid integer"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Starting AI analysis for user {request.user.id} with {days} days")
            
            # Trigger the analysis
            analysis = ai_service.analyze_user_data(request.user, days)
            
            if analysis and analysis.get("analysis_successful", False):
                return Response({
                    "message": "Analysis completed successfully",
                    "analysis_id": analysis.get("id"),
                    "recommendations_created": analysis.get("recommendations_created", 0),
                    "mood_score": analysis.get("mood_score"),
                    "sentiment_score": analysis.get("sentiment_score"),
                    "needs_attention": analysis.get("needs_attention", False),
                    "data_points": analysis.get("data_points", 0),
                    "analysis_method": analysis.get("analysis_method", "unknown"),
                    "suggestions": analysis.get("suggestions", [])
                })
            else:
                error_message = analysis.get("error", "Analysis failed") if analysis else "Analysis service unavailable"
                return Response(
                    {
                        "error": error_message,
                        "analysis_successful": False,
                        "recommendations_created": 0
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error triggering analysis: {str(e)}", exc_info=True)
            return Response(
                {
                    "error": "Internal server error during analysis",
                    "analysis_successful": False,
                    "recommendations_created": 0
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TherapyRecommendationViewSet(viewsets.ViewSet):
    """ViewSet for therapy recommendations"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List therapy recommendations for the current user"""
        try:
            recommendations = TherapyRecommendation.objects.filter(
                user=request.user
            ).order_by('-created_at')[:10]
            serializer = TherapyRecommendationSerializer(recommendations, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing recommendations: {str(e)}")
            return Response(
                {"error": "Failed to retrieve recommendations"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, pk=None):
        """Retrieve a specific recommendation"""
        try:
            recommendation = TherapyRecommendation.objects.get(pk=pk, user=request.user)
            serializer = TherapyRecommendationSerializer(recommendation)
            return Response(serializer.data)
        except TherapyRecommendation.DoesNotExist:
            return Response(
                {"error": "Recommendation not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def mark_implemented(self, request, pk=None):
        """Mark a recommendation as implemented"""
        try:
            recommendation = TherapyRecommendation.objects.get(pk=pk, user=request.user)
            recommendation.is_implemented = True
            recommendation.save()
            return Response({"message": "Recommendation marked as implemented"})
        except TherapyRecommendation.DoesNotExist:
            return Response(
                {"error": "Recommendation not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def rate_effectiveness(self, request, pk=None):
        """Rate the effectiveness of a recommendation"""
        try:
            recommendation = TherapyRecommendation.objects.get(pk=pk, user=request.user)
            rating = int(request.data.get('rating', 0))
            
            if not 1 <= rating <= 5:
                return Response(
                    {"error": "Rating must be between 1 and 5"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            recommendation.effectiveness_rating = rating
            recommendation.save()
            return Response({"message": "Rating saved successfully"})
        except TherapyRecommendation.DoesNotExist:
            return Response(
                {"error": "Recommendation not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {"error": "Invalid rating value"},
                status=status.HTTP_400_BAD_REQUEST
            )


class CommunicationAnalysisViewSet(viewsets.ViewSet):
    """ViewSet for communication pattern analysis"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List communication analyses for the current user"""
        try:
            analyses = CommunicationPatternAnalysis.objects.filter(
                user=request.user
            ).order_by('-analysis_date')[:10]
            serializer = CommunicationPatternAnalysisSerializer(analyses, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing communication analyses: {str(e)}")
            return Response(
                {"error": "Failed to retrieve analyses"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, pk=None):
        """Retrieve a specific communication analysis"""
        try:
            analysis = CommunicationPatternAnalysis.objects.get(pk=pk, user=request.user)
            serializer = CommunicationPatternAnalysisSerializer(analysis)
            return Response(serializer.data)
        except CommunicationPatternAnalysis.DoesNotExist:
            return Response(
                {"error": "Analysis not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'])
    def analyze_patterns(self, request):
        """Analyze communication patterns for the current user"""
        try:
            days = int(request.data.get('days', 30))
            
            # Use the communication analysis service
            analysis_result = communication_analysis_service.analyze_patterns(
                request.user, days
            )
            
            if analysis_result.get("error"):
                return Response(
                    {"error": analysis_result.get("message", "Analysis failed")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if not analysis_result.get("has_data", True):
                return Response(
                    {
                        "message": analysis_result.get("message", "No communication data available for analysis"),
                        "suggestions": analysis_result.get("suggestions", [])
                    },
                    status=status.HTTP_200_OK
                )
            
            return Response(analysis_result)
            
        except ValueError:
            return Response(
                {"error": "Invalid days parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error analyzing communication patterns: {str(e)}")
            return Response(
                {"error": "Failed to analyze communication patterns"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def therapeutic_relationship(self, request):
        """Get therapeutic relationship analysis"""
        try:
            relationship_data = communication_analysis_service.get_therapeutic_relationship_data(
                request.user
            )
            
            if relationship_data.get("error"):
                return Response(
                    {"error": relationship_data.get("message", "Analysis failed")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if not relationship_data.get("has_relationships", True):
                return Response(
                    {
                        "message": relationship_data.get("message", "No therapeutic relationship data found"),
                        "suggestions": relationship_data.get("suggestions", [])
                    },
                    status=status.HTTP_200_OK
                )
            
            return Response(relationship_data)
            
        except Exception as e:
            logger.error(f"Error getting therapeutic relationship data: {str(e)}")
            return Response(
                {"error": "Failed to retrieve therapeutic relationship data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def analyze_user(self, request):
        """Analyze user communication patterns - alias for analyze_patterns"""
        try:
            days = int(request.data.get('days', 30))
            
            # Use the communication analysis service
            analysis_result = communication_analysis_service.analyze_patterns(
                request.user, days
            )
            
            if analysis_result.get("error"):
                return Response(
                    {"error": analysis_result.get("message", "Analysis failed")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if not analysis_result.get("has_data", True):
                return Response(
                    {
                        "message": analysis_result.get("message", "No communication data available for analysis"),
                        "suggestions": analysis_result.get("suggestions", [])
                    },
                    status=status.HTTP_200_OK
                )
            
            # Add additional metadata for the analyze_user endpoint
            analysis_result.update({
                "analysis_type": "communication_patterns",
                "endpoint": "analyze_user", 
                "user_id": request.user.id
            })
            
            return Response(analysis_result)
            
        except ValueError:
            return Response(
                {"error": "Invalid days parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error analyzing user communication: {str(e)}")
            return Response(
                {"error": "Failed to analyze user communication patterns"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TipsViewSet(viewsets.ViewSet):
    """ViewSet for generating personalized tips and suggestions"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def mood(self, request):
        """Generate mood-based tips and suggestions"""
        try:
            # Get query parameters
            days = int(request.query_params.get('days', 7))
            tip_count = int(request.query_params.get('count', 5))
            
            # For now, return sample data since tips_service is not implemented
            tips_data = {
                "tips": [
                    {
                        "title": "Practice Deep Breathing",
                        "description": "Take 5-10 minutes to practice deep breathing exercises to help regulate your mood and reduce stress.",
                        "category": "mindfulness",
                        "difficulty": "easy",
                        "estimated_time": "5-10 minutes",
                        "expected_benefit": "Reduced stress and improved emotional regulation"
                    },
                    {
                        "title": "Go for a Short Walk",
                        "description": "A brief 10-15 minute walk can help boost your mood and provide fresh perspective.",
                        "category": "activity",
                        "difficulty": "easy",
                        "estimated_time": "10-15 minutes",
                        "expected_benefit": "Improved mood and increased energy"
                    }
                ],
                "mood_analysis": {"status": "sample_data"},
                "analysis_period": f"{days} days",
                "generated_at": timezone.now().isoformat(),
                "tip_count": 2,
            }
            
            return Response(tips_data, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response(
                {"error": "Invalid parameters. Days and count must be integers."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating mood tips: {str(e)}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def journaling(self, request):
        """Generate journaling-based tips and suggestions"""
        try:
            # Get query parameters
            days = int(request.query_params.get('days', 14))
            tip_count = int(request.query_params.get('count', 5))
            
            # Sample journaling tips
            tips_data = {
                "tips": [
                    {
                        "title": "Set a Daily Writing Routine",
                        "description": "Try to write in your journal at the same time each day to build consistency and make it a habit.",
                        "category": "habit",
                        "difficulty": "easy",
                        "estimated_time": "10 minutes",
                        "expected_benefit": "Better emotional processing and self-awareness"
                    },
                    {
                        "title": "Use Gratitude Prompts",
                        "description": "End each journal entry with three things you're grateful for to focus on positive aspects of your day.",
                        "category": "reflection",
                        "difficulty": "easy",
                        "estimated_time": "5 minutes",
                        "expected_benefit": "Increased positive focus and emotional balance"
                    }
                ],
                "journal_analysis": {"status": "sample_data"},
                "analysis_period": f"{days} days",
                "generated_at": timezone.now().isoformat(),
                "tip_count": 2,
            }
            
            return Response(tips_data, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response(
                {"error": "Invalid parameters. Days and count must be integers."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating journaling tips: {str(e)}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def combined(self, request):
        """Generate combined tips based on both mood and journal data"""
        try:
            # Get query parameters
            days = int(request.query_params.get('days', 14))
            tip_count = int(request.query_params.get('count', 8))
            
            # Sample combined tips
            tips_data = {
                "tips": [
                    {
                        "title": "Create a Wellness Routine",
                        "description": "Combine mood tracking with journaling for better self-awareness and emotional regulation.",
                        "category": "holistic",
                        "difficulty": "medium",
                        "estimated_time": "15-20 minutes",
                        "expected_benefit": "Improved overall wellbeing and self-understanding"
                    },
                    {
                        "title": "Practice Mindful Reflection",
                        "description": "Before logging your mood, take a moment to reflect on what influenced your feelings today.",
                        "category": "mindfulness",
                        "difficulty": "medium",
                        "estimated_time": "10 minutes",
                        "expected_benefit": "Better emotional awareness and mood management"
                    }
                ],
                "mood_analysis": {"status": "sample_data"},
                "journal_analysis": {"status": "sample_data"},
                "combined_insights": {"overall_wellbeing": "developing"},
                "analysis_period": f"{days} days",
                "generated_at": timezone.now().isoformat(),
                "tip_count": 2,
            }
            
            return Response(tips_data, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response(
                {"error": "Invalid parameters. Days and count must be integers."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating combined tips: {str(e)}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
