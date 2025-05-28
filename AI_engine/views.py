# AI_engine/views.py
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

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
from .services import AIAnalysisService, ai_service
from .services.communication_analysis import communication_analysis_service
from AI_engine.services.predictive_service import predictive_service

logger = logging.getLogger(__name__)


class AIAnalysisViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserAnalysisSerializer

    def get_queryset(self):
        return UserAnalysis.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def analyze_data(self, request):
        """Trigger a new analysis of user's data"""
        try:
            service = AIAnalysisService()
            date_range = request.data.get("date_range", 30)

            # Validate date_range
            if not isinstance(date_range, int) or date_range < 1 or date_range > 365:
                return Response(
                    {"error": "Invalid date_range. Must be between 1 and 365 days."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            analysis = service.analyze_user_data(request.user, date_range)

            if analysis:
                # If analysis is a model instance, serialize it
                if hasattr(analysis, "id"):
                    serializer = self.get_serializer(analysis)
                    return Response(serializer.data)
                # If analysis is a dictionary, return it directly
                elif isinstance(analysis, dict):
                    return Response(analysis)
                else:
                    return Response(
                        {"error": "Invalid analysis format"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            return Response(
                {"error": "Could not generate analysis"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Error in analyze_data: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """Get the latest analysis"""
        analysis = self.get_queryset().first()
        if analysis:
            serializer = self.get_serializer(analysis)
            return Response(serializer.data)
        return Response(
            {"error": "No analysis found"}, status=status.HTTP_404_NOT_FOUND
        )


class AIInsightViewSet(viewsets.ViewSet):
    """
    A viewset for viewing AI insights.

    Instead of using ReadOnlyModelViewSet which causes schema generation issues,
    we're using a basic ViewSet and implementing only the methods we need.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AIInsightSerializer

    def get_queryset(self):
        """Get insights for the authenticated user"""
        return AIInsight.objects.filter(user=self.request.user).order_by("-created_at")

    def get_object(self):
        """Get a specific insight"""
        queryset = self.get_queryset()
        obj = queryset.get(pk=self.kwargs["pk"])
        return obj

    def list(self, request):
        """List all insights for the user"""
        queryset = self.get_queryset()
        serializer = AIInsightSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Retrieve a specific insight"""
        try:
            instance = self.get_object()
            serializer = AIInsightSerializer(instance)
            return Response(serializer.data)
        except AIInsight.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"])
    def mark_addressed(self, request, pk=None):
        """Mark an insight as addressed"""
        insight = self.get_object()
        insight.is_addressed = True
        insight.save()
        serializer = AIInsightSerializer(insight)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def chatbot_context(self, request):
        """Get AI insights for chatbot context with optimized caching"""
        try:
            user_id = request.user.id
            cache_key = f"chatbot_context_{user_id}"
            cache_timeout = settings.AI_ENGINE_SETTINGS.get(
                "CACHE_TIMEOUT", 900
            )  # 15 minutes default

            # Check if user just logged mood or added journal - invalidate cache if needed
            last_activity = self._get_user_last_activity(request.user)
            cache_meta_key = f"chatbot_context_meta_{user_id}"
            last_cached_activity = cache.get(cache_meta_key)

            context = None
            if (
                last_cached_activity
                and last_activity
                and last_cached_activity >= last_activity
            ):
                # Cache is still valid, try to get it
                context = cache.get(cache_key)

            if not context:
                # Get fresh analysis - access ai_service directly for more control
                from AI_engine.services.ai_analysis import ai_service

                # Define shorter context window for chatbot (7 days instead of 30)
                context = ai_service.get_chatbot_context(request.user, date_range=7)

                # Add medication context, ensuring robust error handling
                try:
                    from AI_engine.services.medication_analysis import (
                        medication_analysis_service,
                    )

                    med_context = (
                        medication_analysis_service.analyze_medication_effects(
                            request.user, days=7
                        )
                    )
                    if med_context.get("success"):
                        context["medication_context"] = {
                            "current_medications": med_context.get("medications", []),
                            "effects": med_context.get("mood_effects", {}),
                            "side_effects": med_context.get(
                                "side_effects_detected", []
                            ),
                            "recommendations": med_context.get("recommendations", []),
                        }
                except Exception as e:
                    logger.error(f"Error adding medication context: {str(e)}")

                # Add mood prediction from predictive service
                try:
                    mood_prediction = predictive_service.predict_mood_decline(
                        request.user
                    )
                    context["mood_prediction"] = mood_prediction
                except Exception as e:
                    logger.error(f"Error getting mood prediction: {str(e)}")

                # Add journal analysis from predictive service
                try:
                    journal_analysis = predictive_service.analyze_journal_patterns(
                        request.user
                    )
                    context["journal_analysis"] = journal_analysis
                except Exception as e:
                    logger.error(f"Error analyzing journal patterns: {str(e)}")

                # Add therapy insights if patient profile exists
                try:
                    if hasattr(request.user, "patient_profile"):
                        from AI_engine.services.therapy_analysis import therapy_analysis

                        therapy_insights = therapy_analysis.recommend_session_focus(
                            request.user
                        )
                        context["therapy_insights"] = therapy_insights
                except Exception as e:
                    logger.error(f"Error getting therapy insights: {str(e)}")

                # Store current activity timestamp with cache
                cache.set(cache_meta_key, timezone.now(), timeout=cache_timeout)

                # Cache the result - use shorter timeout for more dynamic data
                cache.set(cache_key, context, timeout=cache_timeout)

            return Response(context)

        except Exception as e:
            logger.error(f"Error getting chatbot context: {str(e)}", exc_info=True)
            return Response(
                {"error": "Could not retrieve AI context"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_user_last_activity(self, user):
        """Get user's last activity timestamp from mood logs and journal entries"""
        try:
            from mood.models import MoodLog
            from journal.models import JournalEntry

            last_mood = MoodLog.objects.filter(user=user).order_by("-logged_at").first()
            last_journal = (
                JournalEntry.objects.filter(user=user).order_by("-created_at").first()
            )

            timestamps = []
            if last_mood:
                timestamps.append(last_mood.logged_at)
            if last_journal:
                timestamps.append(last_journal.created_at)

            if timestamps:
                return max(timestamps)
            return None
        except Exception:
            return None

    @action(detail=False, methods=["post"])
    def analyze_user(self, request):
        """Trigger a new analysis for the user"""
        try:
            analysis = ai_service.analyze_user_data(request.user)
            if analysis:
                return Response(
                    {
                        "status": "success",
                        "analysis": analysis,
                    }
                )
            return Response(
                {"error": "Could not generate analysis"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Error in analyze_user: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TherapyRecommendationViewSet(viewsets.ViewSet):
    """
    A viewset for handling therapy recommendations.

    Instead of using ReadOnlyModelViewSet which causes schema generation issues,
    we're using a basic ViewSet and implementing only the methods we need.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TherapyRecommendationSerializer

    def get_queryset(self):
        """Get therapy recommendations for the authenticated user"""
        return TherapyRecommendation.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )

    def get_object(self):
        """Get a specific recommendation"""
        queryset = self.get_queryset()
        obj = queryset.get(pk=self.kwargs["pk"])
        return obj

    def list(self, request):
        """List all recommendations for the user"""
        queryset = self.get_queryset()
        serializer = TherapyRecommendationSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Retrieve a specific recommendation"""
        try:
            instance = self.get_object()
            serializer = TherapyRecommendationSerializer(instance)
            return Response(serializer.data)
        except TherapyRecommendation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"])
    def mark_implemented(self, request, pk=None):
        """Mark a recommendation as implemented"""
        try:
            recommendation = self.get_object()
            recommendation.is_implemented = True
            recommendation.save()
            serializer = TherapyRecommendationSerializer(recommendation)
            return Response(serializer.data)
        except TherapyRecommendation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"])
    def rate_effectiveness(self, request, pk=None):
        """Rate the effectiveness of a recommendation"""
        try:
            recommendation = self.get_object()
            rating = request.data.get("rating")
            if rating is not None and 1 <= rating <= 5:
                recommendation.effectiveness_rating = rating
                recommendation.save()
                serializer = TherapyRecommendationSerializer(recommendation)
                return Response(serializer.data)
            return Response(
                {"error": "Invalid rating. Must be between 1 and 5"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TherapyRecommendation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class CommunicationAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for communication pattern analysis"""

    serializer_class = CommunicationPatternAnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CommunicationPatternAnalysis.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def analyze_patterns(self, request):
        """Trigger communication pattern analysis for the user"""
        try:
            days = request.data.get("days", 30)
            analysis = communication_analysis_service.analyze_communication_patterns(
                request.user, days=days
            )

            if "error" in analysis:
                return Response(
                    {"error": analysis["error"]}, status=status.HTTP_400_BAD_REQUEST
                )

            return Response(analysis, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def therapeutic_relationship(self, request):
        """Analyze therapeutic relationship with a specific therapist"""
        therapist_id = request.query_params.get("therapist_id")
        if not therapist_id:
            return Response(
                {"error": "therapist_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            analysis = communication_analysis_service.analyze_therapeutic_relationship(
                request.user, therapist_id
            )
            return Response(analysis, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
