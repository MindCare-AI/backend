# AI_engine/services/social_analysis.py
from typing import Dict, List, Any
import logging
from django.conf import settings
import requests
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from ..models import SocialInteractionAnalysis

logger = logging.getLogger(__name__)


class SocialInteractionAnalysisService:
    """Service to analyze user's social interactions in the feeds app."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"
        self.analysis_period = 30  # Default analysis period in days

    def analyze_social_interactions(self, user, days: int = None) -> Dict[str, Any]:
        """
        Analyze a user's social interactions in the feeds app.

        This looks at posts, comments, likes, and reactions to identify:
        - Content that resonates with the user (therapeutic content)
        - User's support network and interaction patterns
        - Correlation between social activity and mood
        """
        try:
            analysis_period = days or self.analysis_period
            end_date = timezone.now()
            start_date = end_date - timedelta(days=analysis_period)

            # Import here to avoid circular imports
            from feeds.models import Post, Comment, Like
            from mood.models import MoodLog

            # Get the user's interactions data
            created_posts = Post.objects.filter(
                creator=user, created_at__range=(start_date, end_date)
            ).prefetch_related("likes", "comments")

            received_comments = Comment.objects.filter(
                post__creator=user, created_at__range=(start_date, end_date)
            ).select_related("creator")

            given_comments = Comment.objects.filter(
                creator=user, created_at__range=(start_date, end_date)
            ).select_related("post", "post__creator")

            given_likes = Like.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).select_related("post", "post__creator")

            received_likes = Like.objects.filter(
                post__creator=user, created_at__range=(start_date, end_date)
            ).select_related("user")

            # Get mood data for correlation analysis
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("logged_at")

            # Prepare interaction data for analysis
            interaction_data = {
                "created_posts": [
                    {
                        "id": post.id,
                        "content": post.content[:200],
                        "likes_count": post.likes.count(),
                        "comments_count": post.comments.count(),
                        "created_at": post.created_at.isoformat(),
                        "topics": post.topics
                        if hasattr(post, "topics") and post.topics
                        else [],
                    }
                    for post in created_posts
                ],
                "received_comments": [
                    {
                        "id": comment.id,
                        "content": comment.content[:100],
                        "commenter": comment.creator.username,
                        "created_at": comment.created_at.isoformat(),
                    }
                    for comment in received_comments
                ],
                "given_comments": [
                    {
                        "id": comment.id,
                        "post_creator": comment.post.creator.username,
                        "content": comment.content[:100],
                        "created_at": comment.created_at.isoformat(),
                    }
                    for comment in given_comments
                ],
                "received_likes_count": received_likes.count(),
                "given_likes_count": given_likes.count(),
                "mood_data": [
                    {"rating": log.mood_rating, "logged_at": log.logged_at.isoformat()}
                    for log in mood_logs
                ],
            }

            # Use Ollama to generate insights
            analysis = self._analyze_with_ollama(interaction_data)

            # Create and return the analysis
            social_analysis = SocialInteractionAnalysis.objects.create(
                user=user,
                analysis_date=timezone.now().date(),
                engagement_score=analysis.get("engagement_score", 0),
                therapeutic_content=analysis.get("therapeutic_content", []),
                support_network=analysis.get("support_network", {}),
                interaction_patterns=analysis.get("interaction_patterns", {}),
                growth_areas=analysis.get("growth_areas", []),
                suggested_interventions=analysis.get("suggested_interventions", []),
            )

            return {
                "id": social_analysis.id,
                "engagement_score": social_analysis.engagement_score,
                "therapeutic_content": social_analysis.therapeutic_content,
                "support_network": social_analysis.support_network,
                "interaction_patterns": social_analysis.interaction_patterns,
                "growth_areas": social_analysis.growth_areas,
                "suggested_interventions": social_analysis.suggested_interventions,
            }

        except Exception as e:
            logger.error(
                f"Error analyzing social interactions: {str(e)}", exc_info=True
            )
            return self._create_default_analysis()

    def _analyze_with_ollama(self, data: Dict) -> Dict:
        """Analyze social interaction data using Ollama"""
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
        """Build prompt for Ollama social interaction analysis"""
        return f"""As an AI analyst, analyze the following user's social interactions and provide insights:

Posts Created: {data['created_posts']}
Comments Received: {data['received_comments']}
Comments Made: {data['given_comments']}
Likes Received: {data['received_likes_count']}
Likes Given: {data['given_likes_count']}
Mood Data: {data['mood_data']}

Analyze this data and provide insights in JSON format with these fields:
{{
    "engagement_score": <float between 0 and 1 representing overall engagement level>,
    "interaction_patterns": {{<key patterns in how the user interacts>}},
    "therapeutic_content": [<list of content topics that seem most beneficial>],
    "support_network": {{<analysis of the user's support connections>}},
    "content_preferences": {{<types of content the user engages with most>}},
    "mood_correlation": {{<correlation between social activity and mood>}},
    "needs_attention": <boolean indicating if there are patterns that need attention>,
    "attention_reason": <if needs_attention is true, the reason>,
    "attention_description": <description of the pattern needing attention>,
    "suggestions": [<list of suggestions for improving social interactions>]
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
                "engagement_score",
                "interaction_patterns",
                "therapeutic_content",
                "support_network",
                "content_preferences",
                "mood_correlation",
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
            "engagement_score": 0.5,
            "interaction_patterns": {
                "posting_frequency": "moderate",
                "commenting_style": "supportive",
            },
            "therapeutic_content": ["supportive_messages"],
            "support_network": {"active_connections": 0},
            "content_preferences": {"general": "neutral"},
            "mood_correlation": {"correlation": "unknown"},
            "needs_attention": False,
        }

    def correlate_with_mood(self, user, days: int = 30) -> Dict[str, Any]:
        """
        Correlate social interaction patterns with mood data

        This helps identify which social interactions positively or negatively
        affect the user's mood
        """
        try:
            from mood.models import MoodLog
            from feeds.models import Post, Comment, Like

            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Get mood logs with dates
            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("logged_at")

            # Get social activity counts per day
            social_activity = {}

            # Count posts, comments, likes per day
            for single_date in (start_date + timedelta(n) for n in range(days)):
                date_str = single_date.date().isoformat()
                social_activity[date_str] = {
                    "posts_created": Post.objects.filter(
                        creator=user, created_at__date=single_date.date()
                    ).count(),
                    "comments_given": Comment.objects.filter(
                        creator=user, created_at__date=single_date.date()
                    ).count(),
                    "comments_received": Comment.objects.filter(
                        post__creator=user, created_at__date=single_date.date()
                    ).count(),
                    "likes_given": Like.objects.filter(
                        user=user, created_at__date=single_date.date()
                    ).count(),
                    "likes_received": Like.objects.filter(
                        post__creator=user, created_at__date=single_date.date()
                    ).count(),
                }

            # Map mood logs to the same days
            mood_by_day = {}
            for log in mood_logs:
                date_str = log.logged_at.date().isoformat()
                if date_str not in mood_by_day:
                    mood_by_day[date_str] = []
                mood_by_day[date_str].append(log.mood_rating)

            # Calculate average mood per day
            for date_str, ratings in mood_by_day.items():
                if date_str in social_activity:
                    social_activity[date_str]["avg_mood"] = sum(ratings) / len(ratings)

            # Simple correlation analysis
            correlations = {
                "high_activity_mood": 0,
                "low_activity_mood": 0,
                "receiving_comments_effect": 0,
                "giving_comments_effect": 0,
                "likes_effect": 0,
            }

            # Calculate basic correlations
            activity_mood_pairs = []
            for date_str, data in social_activity.items():
                if "avg_mood" in data:
                    total_activity = (
                        data["posts_created"]
                        + data["comments_given"]
                        + data["comments_received"]
                        + data["likes_given"]
                        + data["likes_received"]
                    )
                    activity_mood_pairs.append((total_activity, data["avg_mood"]))

            # Simple correlation calculation
            if activity_mood_pairs:
                high_activity_days = [m for a, m in activity_mood_pairs if a > 5]
                low_activity_days = [m for a, m in activity_mood_pairs if a <= 5]

                correlations["high_activity_mood"] = (
                    sum(high_activity_days) / len(high_activity_days)
                    if high_activity_days
                    else 0
                )
                correlations["low_activity_mood"] = (
                    sum(low_activity_days) / len(low_activity_days)
                    if low_activity_days
                    else 0
                )

            return {"day_by_day": social_activity, "correlations": correlations}

        except Exception as e:
            logger.error(
                f"Error correlating social interactions with mood: {str(e)}",
                exc_info=True,
            )
            return {"error": str(e), "success": False}

    def find_therapeutic_content(self, user, min_engagement: int = 3) -> List[Dict]:
        """
        Identify content that has therapeutic value for the user.

        This looks at posts and comments that resulted in positive mood changes
        or had high engagement from the user.
        """
        try:
            from feeds.models import Post, Comment

            # Get posts the user engaged with multiple times
            engaged_post_ids = (
                Comment.objects.filter(creator=user)
                .values("post")
                .annotate(engagement_count=Count("id"))
                .filter(engagement_count__gte=min_engagement)
                .values_list("post", flat=True)
            )

            # Get these posts with their content
            therapeutic_posts = Post.objects.filter(
                id__in=engaged_post_ids
            ).select_related("creator")

            results = []
            for post in therapeutic_posts:
                results.append(
                    {
                        "post_id": post.id,
                        "creator": post.creator.username,
                        "content_summary": post.content[:100]
                        if len(post.content) > 100
                        else post.content,
                        "topics": post.topics if hasattr(post, "topics") else [],
                        "engagement_level": Comment.objects.filter(
                            post=post, creator=user
                        ).count(),
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error finding therapeutic content: {str(e)}", exc_info=True)
            return []


# Create singleton instance
social_analysis_service = SocialInteractionAnalysisService()
