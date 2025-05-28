# AI_engine/services/social_analysis.py
from typing import Dict, List, Any
import logging
from django.conf import settings
import requests
from django.utils import timezone
from datetime import timedelta
import numpy as np
from django.core.cache import cache
import re
from collections import defaultdict
from scipy import stats

logger = logging.getLogger(__name__)


class SocialInteractionAnalysisService:
    """Service to analyze user's social interactions in the feeds app."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "mistral"
        self.analysis_period = 30  # Default analysis period in days
        self.cache_timeout = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "CACHE_TIMEOUT", 900
        )
        self.max_prompt_length = getattr(settings, "AI_ENGINE_SETTINGS", {}).get(
            "MAX_PROMPT_LENGTH", 4000
        )

    def analyze_social_interactions(self, user, days: int = None) -> Dict[str, Any]:
        """Enhanced social interaction analysis with caching and better insights"""
        analysis_period = days or self.analysis_period
        cache_key = f"social_analysis_{user.id}_{analysis_period}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=analysis_period)

            # Import here to avoid circular imports

            # Enhanced data collection with proper error handling
            interaction_data = self._collect_interaction_data(
                user, start_date, end_date
            )

            # Get mood data for correlation analysis
            mood_data = self._collect_mood_data(user, start_date, end_date)

            # Calculate advanced engagement metrics
            engagement_metrics = self._calculate_advanced_engagement_metrics(
                interaction_data
            )

            # Perform content sentiment analysis
            content_analysis = self._analyze_content_sentiment(interaction_data)

            # Network analysis - who does the user interact with most
            network_analysis = self._analyze_social_network(interaction_data)

            # Temporal pattern analysis
            temporal_patterns = self._analyze_temporal_patterns(interaction_data)

            # Combine all data for comprehensive analysis
            comprehensive_data = {
                **interaction_data,
                "mood_data": mood_data,
                "engagement_metrics": engagement_metrics,
                "content_analysis": content_analysis,
                "network_analysis": network_analysis,
                "temporal_patterns": temporal_patterns,
                "analysis_period_days": analysis_period,
            }

            # Use Ollama to generate insights
            analysis = self._analyze_with_ollama(comprehensive_data)

            # Enhanced correlation analysis
            correlation_analysis = self._perform_correlation_analysis(
                interaction_data, mood_data, analysis_period
            )
            analysis.update(correlation_analysis)

            # Store the analysis with enhanced fields
            social_analysis = self._create_analysis_record(user, analysis)

            # Generate alerts if concerning patterns detected
            self._check_for_concerning_patterns(user, analysis)

            # Cache the result
            result = self._format_analysis_result(social_analysis, analysis)
            cache.set(cache_key, result, self.cache_timeout)

            return result

        except Exception as e:
            logger.error(
                f"Error analyzing social interactions: {str(e)}", exc_info=True
            )
            return self._create_default_analysis()

    def _collect_interaction_data(self, user, start_date, end_date) -> Dict[str, Any]:
        """Collect comprehensive interaction data with error handling"""
        try:
            from feeds.models import Post, Comment, Like

            # Get all interaction data with optimized queries
            created_posts = (
                Post.objects.filter(
                    creator=user, created_at__range=(start_date, end_date)
                )
                .prefetch_related("likes", "comments")
                .select_related("creator")
            )

            received_comments = Comment.objects.filter(
                post__creator=user, created_at__range=(start_date, end_date)
            ).select_related("creator", "post")

            given_comments = Comment.objects.filter(
                creator=user, created_at__range=(start_date, end_date)
            ).select_related("post__creator", "post")

            given_likes = Like.objects.filter(
                user=user, created_at__range=(start_date, end_date)
            ).select_related("post__creator", "post")

            received_likes = Like.objects.filter(
                post__creator=user, created_at__range=(start_date, end_date)
            ).select_related("user", "post")

            return {
                "created_posts": self._format_posts_data(created_posts),
                "received_comments": self._format_comments_data(received_comments),
                "given_comments": self._format_comments_data(given_comments),
                "given_likes": self._format_likes_data(given_likes),
                "received_likes": self._format_likes_data(received_likes),
                "total_posts": created_posts.count(),
                "total_given_comments": given_comments.count(),
                "total_received_comments": received_comments.count(),
                "total_given_likes": given_likes.count(),
                "total_received_likes": received_likes.count(),
            }

        except Exception as e:
            logger.error(f"Error collecting interaction data: {str(e)}")
            return self._get_empty_interaction_data()

    def _format_posts_data(self, posts) -> List[Dict]:
        """Format posts data with enhanced metrics"""
        formatted_posts = []
        for post in posts:
            try:
                formatted_posts.append(
                    {
                        "id": post.id,
                        "content": post.content[:200]
                        if len(post.content) > 200
                        else post.content,
                        "content_length": len(post.content),
                        "likes_count": post.likes.count(),
                        "comments_count": post.comments.count(),
                        "engagement_score": post.likes.count() + post.comments.count(),
                        "created_at": post.created_at.isoformat(),
                        "hour_of_day": post.created_at.hour,
                        "day_of_week": post.created_at.weekday(),
                        "topics": getattr(post, "topics", []),
                        "sentiment_keywords": self._extract_sentiment_keywords(
                            post.content
                        ),
                    }
                )
            except Exception as e:
                logger.error(f"Error formatting post {post.id}: {str(e)}")
                continue
        return formatted_posts

    def _format_comments_data(self, comments) -> List[Dict]:
        """Format comments data with enhanced analysis"""
        formatted_comments = []
        for comment in comments:
            try:
                formatted_comments.append(
                    {
                        "id": comment.id,
                        "content": comment.content[:100]
                        if len(comment.content) > 100
                        else comment.content,
                        "content_length": len(comment.content),
                        "commenter": getattr(comment.creator, "username", "Unknown"),
                        "commenter_id": getattr(comment.creator, "id", None),
                        "post_creator": getattr(
                            comment.post.creator, "username", "Unknown"
                        ),
                        "created_at": comment.created_at.isoformat(),
                        "hour_of_day": comment.created_at.hour,
                        "day_of_week": comment.created_at.weekday(),
                        "sentiment_keywords": self._extract_sentiment_keywords(
                            comment.content
                        ),
                        "is_supportive": self._is_supportive_comment(comment.content),
                    }
                )
            except Exception as e:
                logger.error(f"Error formatting comment {comment.id}: {str(e)}")
                continue
        return formatted_comments

    def _format_likes_data(self, likes) -> List[Dict]:
        """Format likes data with timing analysis"""
        formatted_likes = []
        for like in likes:
            try:
                formatted_likes.append(
                    {
                        "id": like.id,
                        "user": getattr(like.user, "username", "Unknown"),
                        "user_id": getattr(like.user, "id", None),
                        "post_creator": getattr(
                            like.post.creator, "username", "Unknown"
                        ),
                        "post_id": like.post.id,
                        "created_at": like.created_at.isoformat(),
                        "hour_of_day": like.created_at.hour,
                        "day_of_week": like.created_at.weekday(),
                    }
                )
            except Exception as e:
                logger.error(f"Error formatting like {like.id}: {str(e)}")
                continue
        return formatted_likes

    def _extract_sentiment_keywords(self, content: str) -> Dict[str, int]:
        """Extract sentiment-related keywords from content"""
        try:
            content_lower = content.lower()

            sentiment_patterns = {
                "positive": [
                    r"\bhappy\b",
                    r"\bgood\b",
                    r"\bgreat\b",
                    r"\bamazing\b",
                    r"\blove\b",
                    r"\bjoy\b",
                ],
                "negative": [
                    r"\bsad\b",
                    r"\bbad\b",
                    r"\bawful\b",
                    r"\bterrible\b",
                    r"\bhate\b",
                    r"\bangry\b",
                ],
                "anxiety": [
                    r"\banxious\b",
                    r"\bworried\b",
                    r"\bstressed\b",
                    r"\bnervous\b",
                ],
                "support": [
                    r"\bsupport\b",
                    r"\bhelp\b",
                    r"\bcare\b",
                    r"\bunderstand\b",
                    r"\bthere for you\b",
                ],
            }

            keyword_counts = {}
            for category, patterns in sentiment_patterns.items():
                count = sum(
                    len(re.findall(pattern, content_lower)) for pattern in patterns
                )
                keyword_counts[category] = count

            return keyword_counts

        except Exception as e:
            logger.error(f"Error extracting sentiment keywords: {str(e)}")
            return {"positive": 0, "negative": 0, "anxiety": 0, "support": 0}

    def _is_supportive_comment(self, content: str) -> bool:
        """Determine if a comment is supportive in nature"""
        try:
            content_lower = content.lower()
            supportive_indicators = [
                r"\bhere for you\b",
                r"\byou can do it\b",
                r"\bproud of you\b",
                r"\bsupport you\b",
                r"\bbelieve in you\b",
                r"\byou\'re not alone\b",
                r"\bunderstand\b",
                r"\bcare about you\b",
                r"\bsending love\b",
            ]

            return any(
                re.search(pattern, content_lower) for pattern in supportive_indicators
            )

        except Exception:
            return False

    def _collect_mood_data(self, user, start_date, end_date) -> List[Dict]:
        """Collect mood data for correlation analysis"""
        try:
            from mood.models import MoodLog

            mood_logs = MoodLog.objects.filter(
                user=user, logged_at__range=(start_date, end_date)
            ).order_by("logged_at")

            return [
                {
                    "rating": log.mood_rating,
                    "logged_at": log.logged_at.isoformat(),
                    "date": log.logged_at.date().isoformat(),
                    "hour": log.logged_at.hour,
                    "day_of_week": log.logged_at.weekday(),
                    "activities": getattr(log, "activities", []),
                    "notes": getattr(log, "notes", ""),
                }
                for log in mood_logs
            ]

        except Exception as e:
            logger.error(f"Error collecting mood data: {str(e)}")
            return []

    def _calculate_advanced_engagement_metrics(self, interaction_data: Dict) -> Dict:
        """Calculate sophisticated engagement metrics"""
        try:
            posts = interaction_data.get("created_posts", [])
            given_comments = interaction_data.get("given_comments", [])
            received_comments = interaction_data.get("received_comments", [])
            given_likes = interaction_data.get("given_likes", [])
            received_likes = interaction_data.get("received_likes", [])

            # Calculate engagement scores
            total_posts = len(posts)
            total_engagement_received = sum(
                post.get("engagement_score", 0) for post in posts
            )
            avg_engagement_per_post = (
                total_engagement_received / total_posts if total_posts > 0 else 0
            )

            # Content quality metrics
            avg_post_length = (
                np.mean([post.get("content_length", 0) for post in posts])
                if posts
                else 0
            )
            avg_comment_length = (
                np.mean(
                    [comment.get("content_length", 0) for comment in given_comments]
                )
                if given_comments
                else 0
            )

            # Interaction ratios
            giving_receiving_ratio = len(given_comments) / max(
                1, len(received_comments)
            )
            likes_comments_ratio = len(given_likes) / max(1, len(given_comments))

            # Supportive behavior
            supportive_comments = sum(
                1 for comment in given_comments if comment.get("is_supportive", False)
            )
            supportive_ratio = (
                supportive_comments / len(given_comments) if given_comments else 0
            )

            return {
                "total_posts": total_posts,
                "avg_engagement_per_post": avg_engagement_per_post,
                "avg_post_length": avg_post_length,
                "avg_comment_length": avg_comment_length,
                "giving_receiving_ratio": giving_receiving_ratio,
                "likes_comments_ratio": likes_comments_ratio,
                "supportive_ratio": supportive_ratio,
                "engagement_consistency": self._calculate_engagement_consistency(posts),
                "interaction_diversity": self._calculate_interaction_diversity(
                    interaction_data
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating engagement metrics: {str(e)}")
            return {}

    def _calculate_engagement_consistency(self, posts: List[Dict]) -> float:
        """Calculate how consistent user's posting engagement is"""
        try:
            if len(posts) < 2:
                return 0.0

            engagement_scores = [post.get("engagement_score", 0) for post in posts]
            if not engagement_scores:
                return 0.0

            mean_engagement = np.mean(engagement_scores)
            std_engagement = np.std(engagement_scores)

            # Lower coefficient of variation indicates higher consistency
            cv = std_engagement / mean_engagement if mean_engagement > 0 else 0
            consistency = max(
                0, 1 - cv
            )  # Convert to 0-1 scale where 1 is most consistent

            return float(consistency)

        except Exception as e:
            logger.error(f"Error calculating engagement consistency: {str(e)}")
            return 0.0

    def _calculate_interaction_diversity(self, interaction_data: Dict) -> float:
        """Calculate diversity of user's social interactions"""
        try:
            # Count unique users interacted with
            unique_users = set()

            for comment in interaction_data.get("given_comments", []):
                if comment.get("post_creator"):
                    unique_users.add(comment["post_creator"])

            for comment in interaction_data.get("received_comments", []):
                if comment.get("commenter"):
                    unique_users.add(comment["commenter"])

            for like in interaction_data.get("given_likes", []):
                if like.get("post_creator"):
                    unique_users.add(like["post_creator"])

            for like in interaction_data.get("received_likes", []):
                if like.get("user"):
                    unique_users.add(like["user"])

            total_interactions = (
                len(interaction_data.get("given_comments", []))
                + len(interaction_data.get("received_comments", []))
                + len(interaction_data.get("given_likes", []))
                + len(interaction_data.get("received_likes", []))
            )

            # Diversity score: unique users / total interactions
            diversity = len(unique_users) / max(1, total_interactions)
            return min(1.0, diversity)  # Cap at 1.0

        except Exception as e:
            logger.error(f"Error calculating interaction diversity: {str(e)}")
            return 0.0

    def _analyze_content_sentiment(self, interaction_data: Dict) -> Dict:
        """Analyze sentiment patterns in user's content"""
        try:
            posts = interaction_data.get("created_posts", [])
            comments = interaction_data.get("given_comments", [])

            all_content_sentiments = []

            # Analyze posts
            for post in posts:
                sentiment = post.get("sentiment_keywords", {})
                all_content_sentiments.append(sentiment)

            # Analyze comments
            for comment in comments:
                sentiment = comment.get("sentiment_keywords", {})
                all_content_sentiments.append(sentiment)

            if not all_content_sentiments:
                return {"overall_sentiment": "neutral", "sentiment_distribution": {}}

            # Aggregate sentiment scores
            total_positive = sum(s.get("positive", 0) for s in all_content_sentiments)
            total_negative = sum(s.get("negative", 0) for s in all_content_sentiments)
            total_anxiety = sum(s.get("anxiety", 0) for s in all_content_sentiments)
            total_support = sum(s.get("support", 0) for s in all_content_sentiments)

            # Determine overall sentiment
            if total_positive > total_negative + total_anxiety:
                overall_sentiment = "positive"
            elif total_negative + total_anxiety > total_positive:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"

            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_distribution": {
                    "positive": total_positive,
                    "negative": total_negative,
                    "anxiety": total_anxiety,
                    "support": total_support,
                },
                "sentiment_ratio": total_positive
                / max(1, total_negative + total_anxiety),
            }

        except Exception as e:
            logger.error(f"Error analyzing content sentiment: {str(e)}")
            return {"overall_sentiment": "neutral", "sentiment_distribution": {}}

    def _analyze_social_network(self, interaction_data: Dict) -> Dict:
        """Analyze user's social network and key relationships"""
        try:
            # Track interactions with each user
            user_interactions = defaultdict(
                lambda: {
                    "comments_to": 0,
                    "comments_from": 0,
                    "likes_to": 0,
                    "likes_from": 0,
                }
            )

            # Count interactions
            for comment in interaction_data.get("given_comments", []):
                user = comment.get("post_creator")
                if user:
                    user_interactions[user]["comments_to"] += 1

            for comment in interaction_data.get("received_comments", []):
                user = comment.get("commenter")
                if user:
                    user_interactions[user]["comments_from"] += 1

            for like in interaction_data.get("given_likes", []):
                user = like.get("post_creator")
                if user:
                    user_interactions[user]["likes_to"] += 1

            for like in interaction_data.get("received_likes", []):
                user = like.get("user")
                if user:
                    user_interactions[user]["likes_from"] += 1

            # Calculate interaction scores
            network_analysis = {}
            for user, interactions in user_interactions.items():
                total_score = (
                    interactions["comments_to"] * 3  # Comments are worth more
                    + interactions["comments_from"] * 3
                    + interactions["likes_to"]
                    + interactions["likes_from"]
                )

                network_analysis[user] = {
                    **interactions,
                    "total_interaction_score": total_score,
                    "is_mutual": interactions["comments_to"] > 0
                    and interactions["comments_from"] > 0,
                    "relationship_strength": self._calculate_relationship_strength(
                        interactions
                    ),
                }

            # Find top connections
            top_connections = sorted(
                network_analysis.items(),
                key=lambda x: x[1]["total_interaction_score"],
                reverse=True,
            )[:5]

            return {
                "total_connections": len(user_interactions),
                "mutual_connections": sum(
                    1 for data in network_analysis.values() if data["is_mutual"]
                ),
                "top_connections": dict(top_connections),
                "network_density": len(user_interactions)
                / max(
                    1,
                    len(interaction_data.get("created_posts", []))
                    + len(interaction_data.get("given_comments", [])),
                ),
                "average_relationship_strength": np.mean(
                    [
                        data["relationship_strength"]
                        for data in network_analysis.values()
                    ]
                )
                if network_analysis
                else 0,
            }

        except Exception as e:
            logger.error(f"Error analyzing social network: {str(e)}")
            return {}

    def _calculate_relationship_strength(self, interactions: Dict) -> float:
        """Calculate the strength of a relationship based on interaction patterns"""
        try:
            # Weight different types of interactions
            comment_weight = 3.0
            like_weight = 1.0
            mutual_bonus = 2.0

            strength = (
                interactions["comments_to"] * comment_weight
                + interactions["comments_from"] * comment_weight
                + interactions["likes_to"] * like_weight
                + interactions["likes_from"] * like_weight
            )

            # Bonus for mutual interactions
            if interactions["comments_to"] > 0 and interactions["comments_from"] > 0:
                strength += mutual_bonus

            # Normalize to 0-10 scale
            return min(10.0, strength / 2.0)

        except Exception:
            return 0.0

    def _analyze_temporal_patterns(self, interaction_data: Dict) -> Dict:
        """Analyze temporal patterns in social interactions"""
        try:
            all_activities = []

            # Collect all timestamped activities
            for post in interaction_data.get("created_posts", []):
                all_activities.append(
                    {
                        "type": "post",
                        "hour": post.get("hour_of_day"),
                        "day_of_week": post.get("day_of_week"),
                        "timestamp": post.get("created_at"),
                    }
                )

            for comment in interaction_data.get("given_comments", []):
                all_activities.append(
                    {
                        "type": "comment",
                        "hour": comment.get("hour_of_day"),
                        "day_of_week": comment.get("day_of_week"),
                        "timestamp": comment.get("created_at"),
                    }
                )

            if not all_activities:
                return {}

            # Analyze patterns
            hour_distribution = defaultdict(int)
            day_distribution = defaultdict(int)

            for activity in all_activities:
                if activity["hour"] is not None:
                    hour_distribution[activity["hour"]] += 1
                if activity["day_of_week"] is not None:
                    day_distribution[activity["day_of_week"]] += 1

            # Find peak activity times
            peak_hour = (
                max(hour_distribution.items(), key=lambda x: x[1])[0]
                if hour_distribution
                else None
            )
            peak_day = (
                max(day_distribution.items(), key=lambda x: x[1])[0]
                if day_distribution
                else None
            )

            return {
                "hour_distribution": dict(hour_distribution),
                "day_distribution": dict(day_distribution),
                "peak_hour": peak_hour,
                "peak_day": peak_day,
                "activity_consistency": self._calculate_temporal_consistency(
                    all_activities
                ),
                "weekend_vs_weekday_ratio": self._calculate_weekend_ratio(
                    day_distribution
                ),
            }

        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {str(e)}")
            return {}

    def _calculate_temporal_consistency(self, activities: List[Dict]) -> float:
        """Calculate how consistent user's activity timing is"""
        try:
            if len(activities) < 2:
                return 0.0

            hours = [
                activity["hour"]
                for activity in activities
                if activity["hour"] is not None
            ]
            if len(hours) < 2:
                return 0.0

            # Calculate standard deviation of activity hours
            std_hours = np.std(hours)
            # Normalize (24 hours max std = 0 consistency, 0 std = 1 consistency)
            consistency = max(0, 1 - (std_hours / 12))

            return float(consistency)

        except Exception:
            return 0.0

    def _calculate_weekend_ratio(self, day_distribution: Dict) -> float:
        """Calculate ratio of weekend to weekday activity"""
        try:
            weekday_activity = sum(
                count for day, count in day_distribution.items() if day < 5
            )  # Monday=0 to Friday=4
            weekend_activity = sum(
                count for day, count in day_distribution.items() if day >= 5
            )  # Saturday=5, Sunday=6

            if weekday_activity == 0:
                return float("inf") if weekend_activity > 0 else 0.0

            return weekend_activity / weekday_activity

        except Exception:
            return 0.0

    def _perform_correlation_analysis(
        self, interaction_data: Dict, mood_data: List[Dict], days: int
    ) -> Dict:
        """Perform statistical correlation analysis between social activity and mood"""
        try:
            if not mood_data:
                return {
                    "correlation_analysis": {
                        "available": False,
                        "reason": "No mood data",
                    }
                }

            # Group mood data by date
            mood_by_date = defaultdict(list)
            for mood in mood_data:
                date = mood["date"]
                mood_by_date[date].append(mood["rating"])

            # Calculate average mood per date
            daily_moods = {}
            for date, ratings in mood_by_date.items():
                daily_moods[date] = np.mean(ratings)

            # Group social activity by date
            daily_activity = defaultdict(int)

            for post in interaction_data.get("created_posts", []):
                date = post["created_at"][:10]  # Extract date part
                daily_activity[date] += 3  # Posts have higher weight

            for comment in interaction_data.get("given_comments", []):
                date = comment["created_at"][:10]
                daily_activity[date] += 2  # Comments have medium weight

            for like in interaction_data.get("given_likes", []):
                date = like["created_at"][:10]
                daily_activity[date] += 1  # Likes have lower weight

            # Find dates with both mood and activity data
            common_dates = set(daily_moods.keys()) & set(daily_activity.keys())

            if len(common_dates) < 3:
                return {
                    "correlation_analysis": {
                        "available": False,
                        "reason": "Insufficient overlapping data",
                    }
                }

            # Prepare data for correlation
            activity_values = [daily_activity[date] for date in common_dates]
            mood_values = [daily_moods[date] for date in common_dates]

            # Calculate correlations
            try:
                correlation_coefficient, p_value = stats.pearsonr(
                    activity_values, mood_values
                )
            except:
                correlation_coefficient, p_value = 0.0, 1.0

            # Analyze patterns
            high_activity_moods = [
                mood_values[i]
                for i, activity in enumerate(activity_values)
                if activity > np.median(activity_values)
            ]
            low_activity_moods = [
                mood_values[i]
                for i, activity in enumerate(activity_values)
                if activity <= np.median(activity_values)
            ]

            return {
                "correlation_analysis": {
                    "available": True,
                    "correlation_coefficient": float(correlation_coefficient),
                    "p_value": float(p_value),
                    "significance": "significant"
                    if p_value < 0.05
                    else "not_significant",
                    "interpretation": self._interpret_correlation(
                        correlation_coefficient, p_value
                    ),
                    "high_activity_avg_mood": np.mean(high_activity_moods)
                    if high_activity_moods
                    else 0,
                    "low_activity_avg_mood": np.mean(low_activity_moods)
                    if low_activity_moods
                    else 0,
                    "sample_size": len(common_dates),
                }
            }

        except Exception as e:
            logger.error(f"Error in correlation analysis: {str(e)}")
            return {
                "correlation_analysis": {
                    "available": False,
                    "reason": f"Analysis error: {str(e)}",
                }
            }

    def _interpret_correlation(self, correlation: float, p_value: float) -> str:
        """Provide human-readable interpretation of correlation"""
        if p_value >= 0.05:
            return "No statistically significant relationship found between social activity and mood"

        if correlation > 0.7:
            return "Strong positive correlation: Higher social activity is associated with better mood"
        elif correlation > 0.3:
            return "Moderate positive correlation: Social activity appears to have a positive effect on mood"
        elif correlation > 0.1:
            return "Weak positive correlation: Some positive relationship between social activity and mood"
        elif correlation < -0.7:
            return "Strong negative correlation: Higher social activity is associated with worse mood"
        elif correlation < -0.3:
            return "Moderate negative correlation: Social activity may have a negative effect on mood"
        elif correlation < -0.1:
            return "Weak negative correlation: Some negative relationship between social activity and mood"
        else:
            return "No meaningful correlation between social activity and mood"

    def _analyze_with_ollama(self, data: Dict) -> Dict:
        """Enhanced Ollama analysis with comprehensive data"""
        try:
            prompt = self._build_enhanced_analysis_prompt(data)

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
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

    def _build_enhanced_analysis_prompt(self, data: Dict) -> str:
        """Build comprehensive prompt for enhanced social analysis"""
        # Limit data size to fit within prompt constraints
        posts_sample = data.get("created_posts", [])[:5]
        comments_sample = data.get("given_comments", [])[:5]

        prompt = f"""As an advanced social interaction analyst, analyze this comprehensive social media data:

POSTS CREATED (sample): {posts_sample}
ENGAGEMENT METRICS: {data.get("engagement_metrics", {})}
CONTENT ANALYSIS: {data.get("content_analysis", {})}
NETWORK ANALYSIS: {data.get("network_analysis", {})}
TEMPORAL PATTERNS: {data.get("temporal_patterns", {})}
CORRELATION ANALYSIS: {data.get("correlation_analysis", {})}

SUMMARY STATISTICS:
- Total posts: {data.get("total_posts", 0)}
- Comments given: {data.get("total_given_comments", 0)}
- Comments received: {data.get("total_received_comments", 0)}
- Likes given: {data.get("total_given_likes", 0)}
- Likes received: {data.get("total_received_likes", 0)}

Provide comprehensive analysis in JSON format:
{{
    "engagement_score": <float 0-1>,
    "social_health_score": <float 0-1>,
    "interaction_patterns": {{<key patterns analysis>}},
    "therapeutic_content": [<beneficial content types>],
    "support_network": {{<support network analysis>}},
    "content_preferences": {{<content engagement preferences>}},
    "mood_correlation": {{<mood-activity correlation insights>}},
    "growth_areas": [<areas for improvement>],
    "suggested_interventions": [<specific intervention suggestions>],
    "risk_factors": [<concerning patterns>],
    "protective_factors": [<positive patterns>],
    "needs_attention": <boolean>,
    "attention_priority": "low|medium|high",
    "recommendations": [<actionable recommendations>]
}}"""

        # Ensure prompt isn't too long
        if len(prompt) > self.max_prompt_length:
            prompt = (
                prompt[: self.max_prompt_length - 100]
                + "...\n\nProvide the JSON analysis."
            )

        return prompt

    def _create_analysis_record(self, user, analysis: Dict):
        """Create enhanced analysis record"""
        try:
            from ..models import SocialInteractionAnalysis

            return SocialInteractionAnalysis.objects.create(
                user=user,
                analysis_date=timezone.now().date(),
                engagement_score=analysis.get("engagement_score", 0.5),
                therapeutic_content=analysis.get("therapeutic_content", []),
                support_network=analysis.get("support_network", {}),
                interaction_patterns=analysis.get("interaction_patterns", {}),
                growth_areas=analysis.get("growth_areas", []),
                suggested_interventions=analysis.get("suggested_interventions", []),
            )

        except Exception as e:
            logger.error(f"Error creating analysis record: {str(e)}")
            return None

    def _check_for_concerning_patterns(self, user, analysis: Dict):
        """Check for concerning patterns and generate alerts"""
        try:
            if analysis.get("needs_attention") and analysis.get(
                "attention_priority"
            ) in ["medium", "high"]:
                from ..models import AIInsight

                AIInsight.objects.create(
                    user=user,
                    insight_type="social_interaction_concern",
                    insight_data={
                        "concern_type": "social_pattern",
                        "risk_factors": analysis.get("risk_factors", []),
                        "recommendations": analysis.get("recommendations", []),
                        "priority": analysis.get("attention_priority", "medium"),
                    },
                    priority=analysis.get("attention_priority", "medium"),
                )

        except Exception as e:
            logger.error(f"Error checking concerning patterns: {str(e)}")

    def _format_analysis_result(self, social_analysis, analysis: Dict) -> Dict:
        """Format the final analysis result"""
        try:
            result = {
                "id": social_analysis.id if social_analysis else None,
                "engagement_score": analysis.get("engagement_score", 0.5),
                "social_health_score": analysis.get("social_health_score", 0.5),
                "therapeutic_content": analysis.get("therapeutic_content", []),
                "support_network": analysis.get("support_network", {}),
                "interaction_patterns": analysis.get("interaction_patterns", {}),
                "growth_areas": analysis.get("growth_areas", []),
                "suggested_interventions": analysis.get("suggested_interventions", []),
                "correlation_analysis": analysis.get("correlation_analysis", {}),
                "recommendations": analysis.get("recommendations", []),
                "needs_attention": analysis.get("needs_attention", False),
                "attention_priority": analysis.get("attention_priority", "low"),
            }

            return result

        except Exception as e:
            logger.error(f"Error formatting analysis result: {str(e)}")
            return self._create_default_analysis()

    def _get_empty_interaction_data(self) -> Dict:
        """Return empty interaction data structure"""
        return {
            "created_posts": [],
            "received_comments": [],
            "given_comments": [],
            "given_likes": [],
            "received_likes": [],
            "total_posts": 0,
            "total_given_comments": 0,
            "total_received_comments": 0,
            "total_given_likes": 0,
            "total_received_likes": 0,
        }
