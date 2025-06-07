# datawarehouse/services/feeds_service.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Any
from django.utils import timezone
from django.db.models import Q
from collections import defaultdict, Counter
import logging
import re
import statistics
import time

logger = logging.getLogger(__name__)


@dataclass
class FeedsDataSnapshot:
    """Data snapshot for feeds/social interaction analytics"""

    # Basic metrics
    total_posts: int
    total_comments: int
    total_reactions: int
    total_active_users: int

    # Content analysis
    content_statistics: Dict[str, Any]
    topic_distribution: Dict[str, Any]
    post_type_analysis: Dict[str, Any]

    # Engagement metrics
    engagement_analytics: Dict[str, Any]
    user_interaction_patterns: Dict[str, Any]
    community_health_metrics: Dict[str, Any]

    # Social dynamics
    social_network_analysis: Dict[str, Any]
    support_interactions: Dict[str, Any]
    mental_health_content: Dict[str, Any]

    # Temporal patterns
    temporal_activity_patterns: Dict[str, Any]
    peak_activity_analysis: Dict[str, Any]

    # Therapeutic value
    therapeutic_content_analysis: Dict[str, Any]
    peer_support_metrics: Dict[str, Any]
    crisis_intervention_indicators: Dict[str, Any]

    # Performance metrics
    analysis_timestamp: datetime
    data_quality_score: float
    cache_performance: Dict[str, Any]


class FeedsCollectionService:
    """Service for collecting and analyzing feeds/social interaction data"""

    def __init__(self):
        self.cache_timeout = 900  # 15 minutes
        self.performance_metrics = {}

    def collect_feeds_data(self, user=None, days: int = 30) -> FeedsDataSnapshot:
        """
        Main entry point for collecting feeds data

        Args:
            user: Specific user to analyze, if None analyze all users
            days: Number of days to look back for analysis

        Returns:
            FeedsDataSnapshot with comprehensive feeds analytics
        """
        start_time = time.time()

        try:
            logger.info(f"Starting feeds data collection for {days} days")

            # Collect raw data
            raw_data = self._collect_raw_feeds_data(user, days)

            # Calculate comprehensive analytics
            content_stats = self._analyze_content_statistics(raw_data)
            engagement_analytics = self._analyze_engagement_patterns(raw_data)
            social_dynamics = self._analyze_social_dynamics(raw_data)
            temporal_patterns = self._analyze_temporal_patterns(raw_data)
            therapeutic_analysis = self._analyze_therapeutic_value(raw_data)

            # Create snapshot
            snapshot = FeedsDataSnapshot(
                total_posts=content_stats["total_posts"],
                total_comments=content_stats["total_comments"],
                total_reactions=content_stats["total_reactions"],
                total_active_users=content_stats["total_active_users"],
                content_statistics=content_stats["content_statistics"],
                topic_distribution=content_stats["topic_distribution"],
                post_type_analysis=content_stats["post_type_analysis"],
                engagement_analytics=engagement_analytics["engagement_metrics"],
                user_interaction_patterns=engagement_analytics["interaction_patterns"],
                community_health_metrics=engagement_analytics["community_health"],
                social_network_analysis=social_dynamics["network_analysis"],
                support_interactions=social_dynamics["support_interactions"],
                mental_health_content=social_dynamics["mental_health_content"],
                temporal_activity_patterns=temporal_patterns["activity_patterns"],
                peak_activity_analysis=temporal_patterns["peak_analysis"],
                therapeutic_content_analysis=therapeutic_analysis[
                    "therapeutic_content"
                ],
                peer_support_metrics=therapeutic_analysis["peer_support"],
                crisis_intervention_indicators=therapeutic_analysis[
                    "crisis_indicators"
                ],
                analysis_timestamp=timezone.now(),
                data_quality_score=self._calculate_data_quality_score(raw_data),
                cache_performance={
                    "collection_time": time.time() - start_time,
                    "data_points_processed": sum(
                        [
                            len(raw_data.get("posts", [])),
                            len(raw_data.get("comments", [])),
                            len(raw_data.get("reactions", [])),
                        ]
                    ),
                    "cache_hits": 0,
                    "cache_misses": 1,
                },
            )

            logger.info(
                f"Feeds data collection completed in {time.time() - start_time:.2f}s"
            )
            return snapshot

        except Exception as e:
            logger.error(f"Error in feeds data collection: {str(e)}")
            raise

    def _collect_raw_feeds_data(self, user, days: int) -> Dict[str, Any]:
        """Collect raw feeds data including posts, comments, and reactions"""
        try:
            from feeds.models import Post, Comment, Reaction, Topic

            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Build query filters
            post_filter = Q(created_at__range=(start_date, end_date))
            comment_filter = Q(created_at__range=(start_date, end_date))
            reaction_filter = Q(created_at__range=(start_date, end_date))

            if user:
                # If analyzing specific user, include their posts and interactions
                post_filter &= Q(author=user)
                comment_filter &= Q(author=user)
                reaction_filter &= Q(user=user)

            # Collect posts with related data
            posts = (
                Post.objects.filter(post_filter)
                .select_related("author")
                .prefetch_related(
                    "reactions", "comments", "media_files", "poll_options"
                )
                .order_by("-created_at")
            )

            # Collect comments
            comments = (
                Comment.objects.filter(comment_filter)
                .select_related("author", "post", "parent")
                .prefetch_related("reactions")
                .order_by("-created_at")
            )

            # Collect reactions
            reactions = (
                Reaction.objects.filter(reaction_filter)
                .select_related("user", "content_type")
                .order_by("-created_at")
            )

            # Collect topics
            topics = Topic.objects.filter(is_active=True)

            return {
                "posts": list(posts),
                "comments": list(comments),
                "reactions": list(reactions),
                "topics": list(topics),
                "start_date": start_date,
                "end_date": end_date,
                "target_user": user,
            }

        except Exception as e:
            logger.error(f"Error collecting raw feeds data: {str(e)}")
            return {}

    def _analyze_content_statistics(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze content statistics and distributions"""
        try:
            posts = raw_data.get("posts", [])
            comments = raw_data.get("comments", [])
            reactions = raw_data.get("reactions", [])

            # Basic counts
            total_posts = len(posts)
            total_comments = len(comments)
            total_reactions = len(reactions)

            # Unique users
            unique_users = set()
            for post in posts:
                if hasattr(post, "author"):
                    unique_users.add(post.author.id)
            for comment in comments:
                if hasattr(comment, "author"):
                    unique_users.add(comment.author.id)
            for reaction in reactions:
                if hasattr(reaction, "user"):
                    unique_users.add(reaction.user.id)

            # Content statistics
            content_stats = self._calculate_content_metrics(posts, comments)

            # Topic distribution
            topic_distribution = self._analyze_topic_distribution(posts)

            # Post type analysis
            post_type_analysis = self._analyze_post_types(posts)

            return {
                "total_posts": total_posts,
                "total_comments": total_comments,
                "total_reactions": total_reactions,
                "total_active_users": len(unique_users),
                "content_statistics": content_stats,
                "topic_distribution": topic_distribution,
                "post_type_analysis": post_type_analysis,
            }

        except Exception as e:
            logger.error(f"Error analyzing content statistics: {str(e)}")
            return {}

    def _calculate_content_metrics(self, posts: List, comments: List) -> Dict[str, Any]:
        """Calculate detailed content metrics"""
        try:
            # Post content analysis
            post_lengths = [
                len(post.content) for post in posts if hasattr(post, "content")
            ]
            post_word_counts = [
                len(post.content.split()) for post in posts if hasattr(post, "content")
            ]

            # Comment content analysis
            comment_lengths = [
                len(comment.content)
                for comment in comments
                if hasattr(comment, "content")
            ]
            comment_word_counts = [
                len(comment.content.split())
                for comment in comments
                if hasattr(comment, "content")
            ]

            # Media analysis
            posts_with_media = sum(
                1
                for post in posts
                if hasattr(post, "media_files") and post.media_files.exists()
            )

            # Link analysis
            posts_with_links = sum(
                1 for post in posts if hasattr(post, "link_url") and post.link_url
            )

            return {
                "avg_post_length": statistics.mean(post_lengths) if post_lengths else 0,
                "median_post_length": statistics.median(post_lengths)
                if post_lengths
                else 0,
                "avg_post_word_count": statistics.mean(post_word_counts)
                if post_word_counts
                else 0,
                "avg_comment_length": statistics.mean(comment_lengths)
                if comment_lengths
                else 0,
                "median_comment_length": statistics.median(comment_lengths)
                if comment_lengths
                else 0,
                "avg_comment_word_count": statistics.mean(comment_word_counts)
                if comment_word_counts
                else 0,
                "posts_with_media_percentage": (posts_with_media / max(1, len(posts)))
                * 100,
                "posts_with_links_percentage": (posts_with_links / max(1, len(posts)))
                * 100,
                "long_posts": sum(1 for length in post_lengths if length > 500),
                "short_posts": sum(1 for length in post_lengths if length < 50),
                "detailed_comments": sum(
                    1 for length in comment_lengths if length > 100
                ),
                "brief_comments": sum(1 for length in comment_lengths if length < 20),
            }

        except Exception as e:
            logger.error(f"Error calculating content metrics: {str(e)}")
            return {}

    def _analyze_topic_distribution(self, posts: List) -> Dict[str, Any]:
        """Analyze distribution of topics in posts"""
        try:
            topic_counts = Counter()
            posts_with_topics = 0

            for post in posts:
                if hasattr(post, "topics") and post.topics:
                    topic_counts[post.topics] += 1
                    posts_with_topics += 1

            total_posts = len(posts)

            # Convert to percentages
            topic_percentages = {}
            for topic, count in topic_counts.items():
                topic_percentages[topic] = (count / max(1, total_posts)) * 100

            return {
                "topic_counts": dict(topic_counts),
                "topic_percentages": topic_percentages,
                "most_popular_topic": topic_counts.most_common(1)[0][0]
                if topic_counts
                else None,
                "posts_with_topics_percentage": (
                    posts_with_topics / max(1, total_posts)
                )
                * 100,
                "topic_diversity": len(topic_counts),
                "posts_without_topics": total_posts - posts_with_topics,
            }

        except Exception as e:
            logger.error(f"Error analyzing topic distribution: {str(e)}")
            return {}

    def _analyze_post_types(self, posts: List) -> Dict[str, Any]:
        """Analyze distribution of post types"""
        try:
            type_counts = Counter()

            for post in posts:
                if hasattr(post, "post_type"):
                    type_counts[post.post_type] += 1

            total_posts = len(posts)

            # Convert to percentages
            type_percentages = {}
            for post_type, count in type_counts.items():
                type_percentages[post_type] = (count / max(1, total_posts)) * 100

            # Analyze polls specifically
            poll_posts = [
                post
                for post in posts
                if hasattr(post, "post_type") and post.post_type == "poll"
            ]
            poll_participation = self._analyze_poll_participation(poll_posts)

            return {
                "type_counts": dict(type_counts),
                "type_percentages": type_percentages,
                "most_common_type": type_counts.most_common(1)[0][0]
                if type_counts
                else None,
                "poll_analysis": poll_participation,
                "media_posts": type_counts.get("image", 0)
                + type_counts.get("video", 0),
                "text_only_posts": type_counts.get("text", 0),
            }

        except Exception as e:
            logger.error(f"Error analyzing post types: {str(e)}")
            return {}

    def _analyze_poll_participation(self, poll_posts: List) -> Dict[str, Any]:
        """Analyze poll participation patterns"""
        try:
            if not poll_posts:
                return {"total_polls": 0, "avg_participation": 0}

            total_votes = 0
            total_options = 0

            for poll in poll_posts:
                if hasattr(poll, "poll_options"):
                    options = poll.poll_options.all()
                    total_options += len(options)
                    for option in options:
                        if hasattr(option, "votes"):
                            total_votes += option.votes.count()

            return {
                "total_polls": len(poll_posts),
                "total_votes": total_votes,
                "total_options": total_options,
                "avg_votes_per_poll": total_votes / max(1, len(poll_posts)),
                "avg_options_per_poll": total_options / max(1, len(poll_posts)),
                "avg_votes_per_option": total_votes / max(1, total_options),
            }

        except Exception as e:
            logger.error(f"Error analyzing poll participation: {str(e)}")
            return {}

    def _analyze_engagement_patterns(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user engagement patterns"""
        try:
            posts = raw_data.get("posts", [])
            comments = raw_data.get("comments", [])
            reactions = raw_data.get("reactions", [])

            # Calculate engagement metrics
            engagement_metrics = self._calculate_engagement_metrics(
                posts, comments, reactions
            )

            # Analyze interaction patterns
            interaction_patterns = self._analyze_interaction_patterns(
                posts, comments, reactions
            )

            # Calculate community health metrics
            community_health = self._calculate_community_health_metrics(
                posts, comments, reactions
            )

            return {
                "engagement_metrics": engagement_metrics,
                "interaction_patterns": interaction_patterns,
                "community_health": community_health,
            }

        except Exception as e:
            logger.error(f"Error analyzing engagement patterns: {str(e)}")
            return {}

    def _calculate_engagement_metrics(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Calculate detailed engagement metrics"""
        try:
            if not posts:
                return {}

            # Post engagement
            post_reaction_counts = []
            post_comment_counts = []
            post_view_counts = []

            for post in posts:
                reaction_count = 0
                comment_count = 0
                view_count = 0

                if hasattr(post, "reactions"):
                    reaction_count = post.reactions.count()
                if hasattr(post, "comments"):
                    comment_count = post.comments.count()
                if hasattr(post, "views_count"):
                    view_count = post.views_count

                post_reaction_counts.append(reaction_count)
                post_comment_counts.append(comment_count)
                post_view_counts.append(view_count)

            # Calculate engagement rates
            avg_reactions_per_post = (
                statistics.mean(post_reaction_counts) if post_reaction_counts else 0
            )
            avg_comments_per_post = (
                statistics.mean(post_comment_counts) if post_comment_counts else 0
            )
            avg_views_per_post = (
                statistics.mean(post_view_counts) if post_view_counts else 0
            )

            # Engagement distribution
            high_engagement_posts = sum(
                1
                for count in post_reaction_counts
                if count > avg_reactions_per_post * 2
            )
            low_engagement_posts = sum(
                1 for count in post_reaction_counts if count == 0
            )

            # Comment engagement
            comment_reaction_counts = []
            for comment in comments:
                if hasattr(comment, "reactions"):
                    comment_reaction_counts.append(comment.reactions.count())

            return {
                "avg_reactions_per_post": avg_reactions_per_post,
                "avg_comments_per_post": avg_comments_per_post,
                "avg_views_per_post": avg_views_per_post,
                "avg_reactions_per_comment": statistics.mean(comment_reaction_counts)
                if comment_reaction_counts
                else 0,
                "high_engagement_posts": high_engagement_posts,
                "low_engagement_posts": low_engagement_posts,
                "engagement_variance": statistics.variance(post_reaction_counts)
                if len(post_reaction_counts) > 1
                else 0,
                "most_engaged_post_reactions": max(post_reaction_counts)
                if post_reaction_counts
                else 0,
                "most_commented_post": max(post_comment_counts)
                if post_comment_counts
                else 0,
                "total_engagement_score": sum(post_reaction_counts)
                + sum(post_comment_counts),
            }

        except Exception as e:
            logger.error(f"Error calculating engagement metrics: {str(e)}")
            return {}

    def _analyze_interaction_patterns(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Analyze user interaction patterns"""
        try:
            # User activity analysis
            user_post_counts = Counter()
            user_comment_counts = Counter()
            user_reaction_counts = Counter()

            for post in posts:
                if hasattr(post, "author"):
                    user_post_counts[post.author.id] += 1

            for comment in comments:
                if hasattr(comment, "author"):
                    user_comment_counts[comment.author.id] += 1

            for reaction in reactions:
                if hasattr(reaction, "user"):
                    user_reaction_counts[reaction.user.id] += 1

            # Calculate activity distributions
            total_users = len(
                set(
                    list(user_post_counts.keys())
                    + list(user_comment_counts.keys())
                    + list(user_reaction_counts.keys())
                )
            )

            # Power user analysis
            power_users = self._identify_power_users(
                user_post_counts, user_comment_counts, user_reaction_counts
            )

            # Interaction diversity
            interaction_diversity = self._calculate_interaction_diversity(
                posts, comments, reactions
            )

            return {
                "total_active_users": total_users,
                "avg_posts_per_user": statistics.mean(list(user_post_counts.values()))
                if user_post_counts
                else 0,
                "avg_comments_per_user": statistics.mean(
                    list(user_comment_counts.values())
                )
                if user_comment_counts
                else 0,
                "avg_reactions_per_user": statistics.mean(
                    list(user_reaction_counts.values())
                )
                if user_reaction_counts
                else 0,
                "power_users": power_users,
                "interaction_diversity": interaction_diversity,
                "lurkers": total_users
                - len(user_post_counts)
                - len(user_comment_counts),
                "creators": len(user_post_counts),
                "commenters": len(user_comment_counts),
                "reactors": len(user_reaction_counts),
            }

        except Exception as e:
            logger.error(f"Error analyzing interaction patterns: {str(e)}")
            return {}

    def _identify_power_users(
        self, post_counts: Counter, comment_counts: Counter, reaction_counts: Counter
    ) -> Dict[str, Any]:
        """Identify power users based on activity"""
        try:
            # Calculate activity scores for each user
            user_scores = defaultdict(int)

            for user_id, count in post_counts.items():
                user_scores[user_id] += count * 3  # Posts weighted higher

            for user_id, count in comment_counts.items():
                user_scores[user_id] += count * 2  # Comments weighted medium

            for user_id, count in reaction_counts.items():
                user_scores[user_id] += count  # Reactions weighted lower

            # Determine thresholds
            if not user_scores:
                return {"power_users": [], "moderate_users": [], "casual_users": []}

            scores = list(user_scores.values())
            avg_score = statistics.mean(scores)

            power_threshold = avg_score * 2
            moderate_threshold = avg_score * 0.5

            power_users = [
                user_id
                for user_id, score in user_scores.items()
                if score > power_threshold
            ]
            moderate_users = [
                user_id
                for user_id, score in user_scores.items()
                if moderate_threshold < score <= power_threshold
            ]
            casual_users = [
                user_id
                for user_id, score in user_scores.items()
                if score <= moderate_threshold
            ]

            return {
                "power_users": len(power_users),
                "moderate_users": len(moderate_users),
                "casual_users": len(casual_users),
                "power_user_percentage": (len(power_users) / len(user_scores)) * 100,
                "avg_activity_score": avg_score,
                "highest_activity_score": max(scores),
                "activity_distribution": {
                    "power": len(power_users),
                    "moderate": len(moderate_users),
                    "casual": len(casual_users),
                },
            }

        except Exception as e:
            logger.error(f"Error identifying power users: {str(e)}")
            return {}

    def _calculate_interaction_diversity(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Calculate diversity of interactions"""
        try:
            # User interaction matrix
            user_interactions = defaultdict(
                lambda: {"posts": 0, "comments": 0, "reactions": 0}
            )

            for post in posts:
                if hasattr(post, "author"):
                    user_interactions[post.author.id]["posts"] += 1

            for comment in comments:
                if hasattr(comment, "author"):
                    user_interactions[comment.author.id]["comments"] += 1

            for reaction in reactions:
                if hasattr(reaction, "user"):
                    user_interactions[reaction.user.id]["reactions"] += 1

            # Calculate diversity scores
            diversity_scores = []
            for user_id, interactions in user_interactions.items():
                total_interactions = sum(interactions.values())
                if total_interactions > 0:
                    # Calculate Shannon diversity index
                    diversity = 0
                    for interaction_type, count in interactions.items():
                        if count > 0:
                            p = count / total_interactions
                            diversity -= p * (
                                p**0.5
                            )  # Simplified diversity calculation
                    diversity_scores.append(diversity)

            return {
                "avg_interaction_diversity": statistics.mean(diversity_scores)
                if diversity_scores
                else 0,
                "users_with_diverse_interactions": sum(
                    1 for score in diversity_scores if score > 0.5
                ),
                "single_interaction_users": sum(
                    1
                    for interactions in user_interactions.values()
                    if sum(1 for count in interactions.values() if count > 0) == 1
                ),
                "multi_interaction_users": sum(
                    1
                    for interactions in user_interactions.values()
                    if sum(1 for count in interactions.values() if count > 0) > 1
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating interaction diversity: {str(e)}")
            return {}

    def _calculate_community_health_metrics(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Calculate community health and toxicity metrics"""
        try:
            # Positive interaction indicators
            positive_reactions = sum(
                1
                for reaction in reactions
                if hasattr(reaction, "reaction_type")
                and reaction.reaction_type in ["love", "support", "celebrate"]
            )

            total_reactions = len(reactions)

            # Supportive content analysis
            supportive_content = self._analyze_supportive_content(posts, comments)

            # Community engagement health
            response_rate = len(comments) / max(1, len(posts))

            # User retention indicators (users active in multiple days)
            user_activity_days = self._calculate_user_activity_spread(
                posts, comments, reactions
            )

            return {
                "positive_reaction_percentage": (
                    positive_reactions / max(1, total_reactions)
                )
                * 100,
                "supportive_content_percentage": supportive_content[
                    "supportive_percentage"
                ],
                "community_response_rate": response_rate,
                "avg_user_activity_days": user_activity_days["avg_activity_days"],
                "consistent_users": user_activity_days["consistent_users"],
                "community_engagement_score": self._calculate_community_engagement_score(
                    positive_reactions,
                    total_reactions,
                    supportive_content,
                    response_rate,
                ),
                "helpful_content_indicators": supportive_content["helpful_indicators"],
                "crisis_support_instances": supportive_content["crisis_support"],
            }

        except Exception as e:
            logger.error(f"Error calculating community health metrics: {str(e)}")
            return {}

    def _analyze_supportive_content(
        self, posts: List, comments: List
    ) -> Dict[str, Any]:
        """Analyze supportive and helpful content"""
        try:
            supportive_keywords = [
                r"\bsupport\b",
                r"\bhelp\b",
                r"\bcare\b",
                r"\bunderstand\b",
                r"\bthere for you\b",
                r"\byou.*not.*alone\b",
                r"\bproud of you\b",
                r"\byou.*can.*do.*it\b",
                r"\bbelieve.*in.*you\b",
                r"\bsending.*love\b",
            ]

            crisis_keywords = [
                r"\bcrisis\b",
                r"\bemergency\b",
                r"\bsuicidal\b",
                r"\bhurt.*myself\b",
                r"\bend.*it.*all\b",
                r"\bhotline\b",
                r"\b911\b",
                r"\bgive.*up\b",
            ]

            helpful_keywords = [
                r"\btip\b",
                r"\badvice\b",
                r"\brecommend\b",
                r"\bsuggestion\b",
                r"\btry.*this\b",
                r"\bworked.*for.*me\b",
                r"\bresource\b",
            ]

            supportive_posts = 0
            supportive_comments = 0
            crisis_support = 0
            helpful_content = 0

            # Analyze posts
            for post in posts:
                if hasattr(post, "content"):
                    content_lower = post.content.lower()

                    if any(
                        re.search(keyword, content_lower)
                        for keyword in supportive_keywords
                    ):
                        supportive_posts += 1

                    if any(
                        re.search(keyword, content_lower) for keyword in crisis_keywords
                    ):
                        crisis_support += 1

                    if any(
                        re.search(keyword, content_lower)
                        for keyword in helpful_keywords
                    ):
                        helpful_content += 1

            # Analyze comments
            for comment in comments:
                if hasattr(comment, "content"):
                    content_lower = comment.content.lower()

                    if any(
                        re.search(keyword, content_lower)
                        for keyword in supportive_keywords
                    ):
                        supportive_comments += 1

                    if any(
                        re.search(keyword, content_lower) for keyword in crisis_keywords
                    ):
                        crisis_support += 1

                    if any(
                        re.search(keyword, content_lower)
                        for keyword in helpful_keywords
                    ):
                        helpful_content += 1

            total_content = len(posts) + len(comments)
            supportive_content_total = supportive_posts + supportive_comments

            return {
                "supportive_posts": supportive_posts,
                "supportive_comments": supportive_comments,
                "supportive_percentage": (
                    supportive_content_total / max(1, total_content)
                )
                * 100,
                "crisis_support": crisis_support,
                "helpful_indicators": helpful_content,
                "supportive_to_total_ratio": supportive_content_total
                / max(1, total_content),
            }

        except Exception as e:
            logger.error(f"Error analyzing supportive content: {str(e)}")
            return {}

    def _calculate_user_activity_spread(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Calculate how consistently users are active"""
        try:
            user_activity_dates = defaultdict(set)

            # Track activity dates for each user
            for post in posts:
                if hasattr(post, "author") and hasattr(post, "created_at"):
                    user_activity_dates[post.author.id].add(post.created_at.date())

            for comment in comments:
                if hasattr(comment, "author") and hasattr(comment, "created_at"):
                    user_activity_dates[comment.author.id].add(
                        comment.created_at.date()
                    )

            for reaction in reactions:
                if hasattr(reaction, "user") and hasattr(reaction, "created_at"):
                    user_activity_dates[reaction.user.id].add(
                        reaction.created_at.date()
                    )

            # Calculate activity spread
            activity_day_counts = [len(dates) for dates in user_activity_dates.values()]
            consistent_users = sum(1 for count in activity_day_counts if count >= 3)

            return {
                "avg_activity_days": statistics.mean(activity_day_counts)
                if activity_day_counts
                else 0,
                "consistent_users": consistent_users,
                "one_day_users": sum(1 for count in activity_day_counts if count == 1),
                "multi_day_users": sum(1 for count in activity_day_counts if count > 1),
                "most_active_user_days": max(activity_day_counts)
                if activity_day_counts
                else 0,
            }

        except Exception as e:
            logger.error(f"Error calculating user activity spread: {str(e)}")
            return {}

    def _calculate_community_engagement_score(
        self,
        positive_reactions: int,
        total_reactions: int,
        supportive_content: Dict,
        response_rate: float,
    ) -> float:
        """Calculate overall community engagement health score"""
        try:
            # Normalize metrics to 0-1 scale
            positive_ratio = positive_reactions / max(1, total_reactions)
            supportive_ratio = supportive_content.get("supportive_to_total_ratio", 0)
            normalized_response_rate = min(
                1.0, response_rate / 2.0
            )  # Normalize response rate

            # Weighted average
            engagement_score = (
                positive_ratio * 0.3
                + supportive_ratio * 0.4
                + normalized_response_rate * 0.3
            )

            return float(engagement_score)

        except Exception as e:
            logger.error(f"Error calculating community engagement score: {str(e)}")
            return 0.0

    def _analyze_social_dynamics(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze social dynamics and network patterns"""
        try:
            posts = raw_data.get("posts", [])
            comments = raw_data.get("comments", [])
            reactions = raw_data.get("reactions", [])

            # Network analysis
            network_analysis = self._calculate_network_metrics(
                posts, comments, reactions
            )

            # Support interactions
            support_interactions = self._analyze_support_interactions(posts, comments)

            # Mental health content analysis
            mental_health_content = self._analyze_mental_health_content(posts, comments)

            return {
                "network_analysis": network_analysis,
                "support_interactions": support_interactions,
                "mental_health_content": mental_health_content,
            }

        except Exception as e:
            logger.error(f"Error analyzing social dynamics: {str(e)}")
            return {}

    def _calculate_network_metrics(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Calculate social network metrics"""
        try:
            # Build interaction graph
            user_connections = defaultdict(set)

            # Comments create connections between users
            for comment in comments:
                if (
                    hasattr(comment, "author")
                    and hasattr(comment, "post")
                    and hasattr(comment.post, "author")
                ):
                    commenter = comment.author.id
                    post_author = comment.post.author.id
                    if commenter != post_author:  # Don't count self-interactions
                        user_connections[commenter].add(post_author)
                        user_connections[post_author].add(commenter)

            # Reactions also create connections
            for reaction in reactions:
                if hasattr(reaction, "user") and hasattr(reaction, "content_object"):
                    reactor = reaction.user.id
                    # Get the author of the content being reacted to
                    content = reaction.content_object
                    if hasattr(content, "author"):
                        content_author = content.author.id
                        if reactor != content_author:
                            user_connections[reactor].add(content_author)
                            user_connections[content_author].add(reactor)

            # Calculate network metrics
            total_users = len(user_connections)
            connection_counts = [
                len(connections) for connections in user_connections.values()
            ]

            # Identify highly connected users
            avg_connections = (
                statistics.mean(connection_counts) if connection_counts else 0
            )
            highly_connected = sum(
                1 for count in connection_counts if count > avg_connections * 2
            )

            return {
                "total_connected_users": total_users,
                "avg_connections_per_user": avg_connections,
                "max_connections": max(connection_counts) if connection_counts else 0,
                "highly_connected_users": highly_connected,
                "isolated_users": sum(1 for count in connection_counts if count == 0),
                "network_density": self._calculate_network_density(user_connections),
                "connection_distribution": {
                    "low": sum(1 for count in connection_counts if count <= 2),
                    "medium": sum(1 for count in connection_counts if 2 < count <= 10),
                    "high": sum(1 for count in connection_counts if count > 10),
                },
            }

        except Exception as e:
            logger.error(f"Error calculating network metrics: {str(e)}")
            return {}

    def _calculate_network_density(self, user_connections: Dict) -> float:
        """Calculate network density"""
        try:
            total_users = len(user_connections)
            if total_users < 2:
                return 0.0

            actual_connections = (
                sum(len(connections) for connections in user_connections.values()) / 2
            )
            possible_connections = (total_users * (total_users - 1)) / 2

            return actual_connections / max(1, possible_connections)

        except Exception as e:
            logger.error(f"Error calculating network density: {str(e)}")
            return 0.0

    def _analyze_support_interactions(
        self, posts: List, comments: List
    ) -> Dict[str, Any]:
        """Analyze peer support interactions"""
        try:
            support_requests = 0
            support_offers = 0
            peer_advice = 0
            encouragement = 0

            request_keywords = [
                r"\bneed.*help\b",
                r"\bstruggling\b",
                r"\badvice\b",
                r"\bwhat.*should.*i.*do\b",
            ]
            offer_keywords = [
                r"\bhere.*for.*you\b",
                r"\bcan.*help\b",
                r"\bpm.*me\b",
                r"\breachout\b",
            ]
            advice_keywords = [
                r"\btry\b",
                r"\bsuggestion\b",
                r"\brecommend\b",
                r"\bworked.*for.*me\b",
            ]
            encouragement_keywords = [
                r"\byou.*can.*do.*it\b",
                r"\bproud.*of.*you\b",
                r"\bkeep.*going\b",
                r"\bstay.*strong\b",
            ]

            all_content = []
            for post in posts:
                if hasattr(post, "content"):
                    all_content.append(post.content)
            for comment in comments:
                if hasattr(comment, "content"):
                    all_content.append(comment.content)

            for content in all_content:
                content_lower = content.lower()

                if any(
                    re.search(keyword, content_lower) for keyword in request_keywords
                ):
                    support_requests += 1
                if any(re.search(keyword, content_lower) for keyword in offer_keywords):
                    support_offers += 1
                if any(
                    re.search(keyword, content_lower) for keyword in advice_keywords
                ):
                    peer_advice += 1
                if any(
                    re.search(keyword, content_lower)
                    for keyword in encouragement_keywords
                ):
                    encouragement += 1

            total_content = len(all_content)

            return {
                "support_requests": support_requests,
                "support_offers": support_offers,
                "peer_advice_instances": peer_advice,
                "encouragement_instances": encouragement,
                "support_request_percentage": (support_requests / max(1, total_content))
                * 100,
                "support_offer_percentage": (support_offers / max(1, total_content))
                * 100,
                "peer_support_ratio": support_offers / max(1, support_requests),
                "total_supportive_interactions": support_offers
                + peer_advice
                + encouragement,
            }

        except Exception as e:
            logger.error(f"Error analyzing support interactions: {str(e)}")
            return {}

    def _analyze_mental_health_content(
        self, posts: List, comments: List
    ) -> Dict[str, Any]:
        """Analyze mental health related content"""
        try:
            mental_health_topics = {
                "anxiety": [
                    r"\banxiety\b",
                    r"\banxious\b",
                    r"\bpanic\b",
                    r"\bworried\b",
                ],
                "depression": [
                    r"\bdepression\b",
                    r"\bdepressed\b",
                    r"\bsad\b",
                    r"\bhopeless\b",
                ],
                "stress": [
                    r"\bstress\b",
                    r"\bstressed\b",
                    r"\boverwhelmed\b",
                    r"\bpressure\b",
                ],
                "therapy": [
                    r"\btherapy\b",
                    r"\btherapist\b",
                    r"\bcounseling\b",
                    r"\bsession\b",
                ],
                "medication": [
                    r"\bmedication\b",
                    r"\bpills\b",
                    r"\bantidepressant\b",
                    r"\bprescription\b",
                ],
                "coping": [
                    r"\bcoping\b",
                    r"\bstrategy\b",
                    r"\bmindfulness\b",
                    r"\bmeditation\b",
                ],
                "recovery": [
                    r"\brecovery\b",
                    r"\bhealing\b",
                    r"\bgetting.*better\b",
                    r"\bprogress\b",
                ],
            }

            topic_counts = defaultdict(int)

            all_content = []
            for post in posts:
                if hasattr(post, "content"):
                    all_content.append(post.content)
            for comment in comments:
                if hasattr(comment, "content"):
                    all_content.append(comment.content)

            for content in all_content:
                content_lower = content.lower()
                for topic, keywords in mental_health_topics.items():
                    if any(re.search(keyword, content_lower) for keyword in keywords):
                        topic_counts[topic] += 1

            total_content = len(all_content)
            mental_health_content_total = sum(topic_counts.values())

            return {
                "topic_distribution": dict(topic_counts),
                "mental_health_content_percentage": (
                    mental_health_content_total / max(1, total_content)
                )
                * 100,
                "most_discussed_topic": max(topic_counts.items(), key=lambda x: x[1])[0]
                if topic_counts
                else None,
                "therapeutic_content_instances": topic_counts.get("therapy", 0)
                + topic_counts.get("coping", 0),
                "crisis_related_content": topic_counts.get("depression", 0)
                + topic_counts.get("anxiety", 0),
                "recovery_focused_content": topic_counts.get("recovery", 0)
                + topic_counts.get("coping", 0),
            }

        except Exception as e:
            logger.error(f"Error analyzing mental health content: {str(e)}")
            return {}

    def _analyze_temporal_patterns(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze temporal activity patterns"""
        try:
            posts = raw_data.get("posts", [])
            comments = raw_data.get("comments", [])
            reactions = raw_data.get("reactions", [])

            # Activity patterns
            activity_patterns = self._calculate_activity_patterns(
                posts, comments, reactions
            )

            # Peak activity analysis
            peak_analysis = self._analyze_peak_activity(posts, comments, reactions)

            return {
                "activity_patterns": activity_patterns,
                "peak_analysis": peak_analysis,
            }

        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {str(e)}")
            return {}

    def _calculate_activity_patterns(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Calculate temporal activity patterns"""
        try:
            # Hour of day analysis
            hourly_activity = defaultdict(int)
            daily_activity = defaultdict(int)

            all_activities = []
            for post in posts:
                if hasattr(post, "created_at"):
                    all_activities.append(post.created_at)
            for comment in comments:
                if hasattr(comment, "created_at"):
                    all_activities.append(comment.created_at)
            for reaction in reactions:
                if hasattr(reaction, "created_at"):
                    all_activities.append(reaction.created_at)

            for activity_time in all_activities:
                hourly_activity[activity_time.hour] += 1
                daily_activity[activity_time.weekday()] += 1

            # Find peak hours and days
            peak_hour = (
                max(hourly_activity.items(), key=lambda x: x[1])[0]
                if hourly_activity
                else None
            )
            peak_day = (
                max(daily_activity.items(), key=lambda x: x[1])[0]
                if daily_activity
                else None
            )

            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]

            return {
                "hourly_distribution": dict(hourly_activity),
                "daily_distribution": dict(daily_activity),
                "peak_hour": peak_hour,
                "peak_day": day_names[peak_day] if peak_day is not None else None,
                "total_activities": len(all_activities),
                "activity_spread": {
                    "hours_active": len(hourly_activity),
                    "days_active": len(daily_activity),
                },
            }

        except Exception as e:
            logger.error(f"Error calculating activity patterns: {str(e)}")
            return {}

    def _analyze_peak_activity(
        self, posts: List, comments: List, reactions: List
    ) -> Dict[str, Any]:
        """Analyze peak activity periods"""
        try:
            # Daily activity counts
            daily_counts = defaultdict(int)

            all_activities = []
            for post in posts:
                if hasattr(post, "created_at"):
                    all_activities.append(post.created_at)
            for comment in comments:
                if hasattr(comment, "created_at"):
                    all_activities.append(comment.created_at)
            for reaction in reactions:
                if hasattr(reaction, "created_at"):
                    all_activities.append(reaction.created_at)

            for activity_time in all_activities:
                daily_counts[activity_time.date()] += 1

            if not daily_counts:
                return {}

            # Calculate peak metrics
            activity_counts = list(daily_counts.values())
            avg_daily_activity = statistics.mean(activity_counts)
            peak_day_activity = max(activity_counts)
            low_activity_days = sum(
                1 for count in activity_counts if count < avg_daily_activity * 0.5
            )
            high_activity_days = sum(
                1 for count in activity_counts if count > avg_daily_activity * 2
            )

            return {
                "avg_daily_activity": avg_daily_activity,
                "peak_day_activity": peak_day_activity,
                "low_activity_days": low_activity_days,
                "high_activity_days": high_activity_days,
                "activity_variance": statistics.variance(activity_counts)
                if len(activity_counts) > 1
                else 0,
                "consistent_activity_days": sum(
                    1
                    for count in activity_counts
                    if avg_daily_activity * 0.8 <= count <= avg_daily_activity * 1.2
                ),
                "total_active_days": len(daily_counts),
            }

        except Exception as e:
            logger.error(f"Error analyzing peak activity: {str(e)}")
            return {}

    def _analyze_therapeutic_value(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze therapeutic value of feeds content"""
        try:
            posts = raw_data.get("posts", [])
            comments = raw_data.get("comments", [])

            # Therapeutic content analysis
            therapeutic_content = self._analyze_therapeutic_content_value(
                posts, comments
            )

            # Peer support metrics
            peer_support = self._calculate_peer_support_metrics(posts, comments)

            # Crisis intervention indicators
            crisis_indicators = self._analyze_crisis_intervention_indicators(
                posts, comments
            )

            return {
                "therapeutic_content": therapeutic_content,
                "peer_support": peer_support,
                "crisis_indicators": crisis_indicators,
            }

        except Exception as e:
            logger.error(f"Error analyzing therapeutic value: {str(e)}")
            return {}

    def _analyze_therapeutic_content_value(
        self, posts: List, comments: List
    ) -> Dict[str, Any]:
        """Analyze therapeutic value of content"""
        try:
            therapeutic_indicators = {
                "insight": [
                    r"\brealized\b",
                    r"\bunderstood\b",
                    r"\binsight\b",
                    r"\blearned\b",
                ],
                "gratitude": [
                    r"\bthankful\b",
                    r"\bgrateful\b",
                    r"\bappreciate\b",
                    r"\bblessed\b",
                ],
                "goal_setting": [r"\bgoal\b", r"\bplan\b", r"\btarget\b", r"\baim\b"],
                "self_reflection": [
                    r"\breflect\b",
                    r"\bthinking.*about\b",
                    r"\blooking.*back\b",
                ],
                "progress": [
                    r"\bprogress\b",
                    r"\bimprovement\b",
                    r"\bbetter\b",
                    r"\bgrowth\b",
                ],
                "coping_strategies": [
                    r"\bcoping\b",
                    r"\bstrategy\b",
                    r"\btechnique\b",
                    r"\bmethod\b",
                ],
            }

            content_scores = defaultdict(int)

            all_content = []
            for post in posts:
                if hasattr(post, "content"):
                    all_content.append(post.content)
            for comment in comments:
                if hasattr(comment, "content"):
                    all_content.append(comment.content)

            for content in all_content:
                content_lower = content.lower()
                for category, keywords in therapeutic_indicators.items():
                    if any(re.search(keyword, content_lower) for keyword in keywords):
                        content_scores[category] += 1

            total_content = len(all_content)
            therapeutic_content_total = sum(content_scores.values())

            return {
                "therapeutic_indicators": dict(content_scores),
                "therapeutic_content_percentage": (
                    therapeutic_content_total / max(1, total_content)
                )
                * 100,
                "most_therapeutic_category": max(
                    content_scores.items(), key=lambda x: x[1]
                )[0]
                if content_scores
                else None,
                "insight_sharing": content_scores.get("insight", 0),
                "goal_oriented_content": content_scores.get("goal_setting", 0),
                "self_reflection_instances": content_scores.get("self_reflection", 0),
            }

        except Exception as e:
            logger.error(f"Error analyzing therapeutic content value: {str(e)}")
            return {}

    def _calculate_peer_support_metrics(
        self, posts: List, comments: List
    ) -> Dict[str, Any]:
        """Calculate peer support effectiveness metrics"""
        try:
            # Analyze supportive responses to distress posts
            distress_keywords = [
                r"\bupset\b",
                r"\bsad\b",
                r"\bworried\b",
                r"\bstressed\b",
                r"\bstruggling\b",
            ]
            support_keywords = [
                r"\bhere.*for.*you\b",
                r"\bsupport\b",
                r"\bhelp\b",
                r"\bcare\b",
            ]

            distress_posts = []
            supportive_responses = 0

            # Identify distress posts
            for post in posts:
                if hasattr(post, "content"):
                    content_lower = post.content.lower()
                    if any(
                        re.search(keyword, content_lower)
                        for keyword in distress_keywords
                    ):
                        distress_posts.append(post)

            # Count supportive responses to distress posts
            for post in distress_posts:
                if hasattr(post, "comments"):
                    for comment in post.comments.all():
                        if hasattr(comment, "content"):
                            content_lower = comment.content.lower()
                            if any(
                                re.search(keyword, content_lower)
                                for keyword in support_keywords
                            ):
                                supportive_responses += 1

            # Response effectiveness
            distress_post_count = len(distress_posts)
            response_rate = supportive_responses / max(1, distress_post_count)

            return {
                "distress_posts_identified": distress_post_count,
                "supportive_responses": supportive_responses,
                "support_response_rate": response_rate,
                "avg_support_per_distress_post": response_rate,
                "peer_support_effectiveness": min(
                    1.0, response_rate / 2.0
                ),  # Normalized score
                "unaddressed_distress_posts": max(
                    0, distress_post_count - supportive_responses
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating peer support metrics: {str(e)}")
            return {}

    def _analyze_crisis_intervention_indicators(
        self, posts: List, comments: List
    ) -> Dict[str, Any]:
        """Analyze crisis intervention needs and responses"""
        try:
            crisis_keywords = [
                r"\bsuicidal\b",
                r"\bend.*it.*all\b",
                r"\bhurt.*myself\b",
                r"\bcrisis\b",
                r"\bemergency\b",
                r"\bcan.*t.*go.*on\b",
                r"\bgive.*up\b",
            ]

            intervention_keywords = [
                r"\bhotline\b",
                r"\b911\b",
                r"\bget.*help\b",
                r"\btalk.*to.*someone\b",
                r"\btherapist\b",
                r"\bcounselor\b",
                r"\bemergency.*room\b",
            ]

            crisis_posts = 0
            crisis_comments = 0
            intervention_responses = 0

            # Identify crisis content
            all_content = []
            for post in posts:
                if hasattr(post, "content"):
                    content = post.content.lower()
                    all_content.append(content)
                    if any(re.search(keyword, content) for keyword in crisis_keywords):
                        crisis_posts += 1

            for comment in comments:
                if hasattr(comment, "content"):
                    content = comment.content.lower()
                    all_content.append(content)
                    if any(re.search(keyword, content) for keyword in crisis_keywords):
                        crisis_comments += 1

            # Count intervention responses
            for content in all_content:
                if any(
                    re.search(keyword, content) for keyword in intervention_keywords
                ):
                    intervention_responses += 1

            total_crisis_content = crisis_posts + crisis_comments

            return {
                "crisis_posts": crisis_posts,
                "crisis_comments": crisis_comments,
                "total_crisis_indicators": total_crisis_content,
                "intervention_responses": intervention_responses,
                "crisis_intervention_ratio": intervention_responses
                / max(1, total_crisis_content),
                "crisis_content_percentage": (
                    total_crisis_content / max(1, len(all_content))
                )
                * 100,
                "intervention_effectiveness": intervention_responses
                / max(1, total_crisis_content),
            }

        except Exception as e:
            logger.error(f"Error analyzing crisis intervention indicators: {str(e)}")
            return {}

    def _calculate_data_quality_score(self, raw_data: Dict[str, Any]) -> float:
        """Calculate overall data quality score"""
        try:
            posts = raw_data.get("posts", [])
            comments = raw_data.get("comments", [])
            reactions = raw_data.get("reactions", [])

            if not posts and not comments and not reactions:
                return 0.0

            # Content completeness
            complete_posts = sum(
                1
                for post in posts
                if hasattr(post, "content")
                and post.content
                and hasattr(post, "author")
                and post.author
            )
            completeness_score = complete_posts / max(1, len(posts))

            # Data richness (average content length)
            post_lengths = [
                len(post.content) for post in posts if hasattr(post, "content")
            ]
            comment_lengths = [
                len(comment.content)
                for comment in comments
                if hasattr(comment, "content")
            ]

            avg_content_length = (
                statistics.mean(post_lengths + comment_lengths)
                if (post_lengths + comment_lengths)
                else 0
            )
            richness_score = min(
                1.0, avg_content_length / 200
            )  # Normalize to 200 chars

            # Engagement quality (content with reactions/comments)
            engaged_posts = sum(
                1
                for post in posts
                if (hasattr(post, "reactions") and post.reactions.count() > 0)
                or (hasattr(post, "comments") and post.comments.count() > 0)
            )
            engagement_score = engaged_posts / max(1, len(posts))

            # Overall quality score
            overall_score = (
                completeness_score * 0.4 + richness_score * 0.3 + engagement_score * 0.3
            )

            return float(overall_score)

        except Exception as e:
            logger.error(f"Error calculating data quality score: {str(e)}")
            return 0.0
