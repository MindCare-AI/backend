from django.db.models import F, Count
from django.contrib.contenttypes.models import ContentType
from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import serializers
from django.db import transaction
from django.core.cache import cache

from feeds.models import Post, Comment, Topic, Reaction
from feeds.serializers import (
    PostSerializer,
    PostDetailSerializer,
    CommentSerializer,
    TopicSerializer,
    ReactionActionSerializer,
    ReactionSerializer,
)
from notifications.models import Notification, NotificationType
from .serializers import LikeToggleSerializer

import logging

logger = logging.getLogger(__name__)


class FeedPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["content", "tags"]
    ordering_fields = ["created_at", "updated_at", "views_count"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        elif self.action == "like":
            return LikeToggleSerializer
        return PostSerializer

    def get_queryset(self):
        queryset = Post.objects.all()
        author = self.request.query_params.get("author")
        if author:
            queryset = queryset.filter(author=author)
        return queryset

    def _apply_filters(self, queryset):
        # Filter by topic
        topic_id = self.request.query_params.get("topic")
        if topic_id:
            queryset = queryset.filter(topics__id=topic_id)

        # Filter by author/user profile
        author_id = self.request.query_params.get("author")
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        # Filter by post type
        post_type = self.request.query_params.get("post_type")
        if post_type:
            queryset = queryset.filter(post_type=post_type)

        # Filter by tags
        tag = self.request.query_params.get("tag")
        if tag:
            queryset = queryset.filter(tags__contains=[tag])

        # Filter for polls only
        polls_only = self.request.query_params.get("polls_only")
        if polls_only and polls_only.lower() == "true":
            queryset = queryset.filter(post_type="poll")

        # Filter for minimum reactions count
        min_reactions = self.request.query_params.get("min_reactions")
        if min_reactions and min_reactions.isdigit():
            queryset = queryset.annotate(total_reactions=Count("reactions")).filter(
                total_reactions__gte=int(min_reactions)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @extend_schema(
        description="React to a post or get post reactions",
        responses={200: OpenApiResponse(description="List of reactions")},
        request=ReactionActionSerializer,
        methods=["POST"],
    )
    @action(
        detail=True, methods=["get", "post"], serializer_class=ReactionActionSerializer
    )
    def react(self, request, pk=None):
        post = self.get_object()
        content_type = ContentType.objects.get_for_model(Post)

        if request.method == "GET":
            reactions = Reaction.objects.filter(
                content_type=content_type, object_id=post.id
            ).select_related("user")

            reaction_data = {}
            for reaction in reactions:
                if reaction.reaction_type not in reaction_data:
                    reaction_data[reaction.reaction_type] = []
                reaction_data[reaction.reaction_type].append(
                    {
                        "user_id": reaction.user.id,
                        "username": reaction.user.username,
                        "timestamp": reaction.created_at,
                    }
                )

            return Response(
                {"reactions": reaction_data, "total_count": reactions.count()}
            )

        # POST method
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reaction_type = serializer.validated_data["reaction_type"]
        reaction, created = Reaction.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=post.id,
            defaults={"reaction_type": reaction_type},
        )

        if not created:
            reaction.reaction_type = reaction_type
            reaction.save()

        if post.author != request.user:
            Notification.objects.create(
                user=post.author,
                notification_type_id=1,  # For reactions
                title=f"{request.user.get_full_name() or request.user.username} reacted to your post",
                content=f"{request.user.get_full_name() or request.user.username} reacted with {reaction_type}",
                is_read=False,
            )

        return Response(
            {
                "detail": "Reaction added successfully"
                if created
                else "Reaction updated successfully",
                "reaction": {
                    "type": reaction.reaction_type,
                    "user": {"id": request.user.id, "username": request.user.username},
                    "created_at": reaction.created_at,
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        description="Remove user's reaction from a post",
        responses={200: {"description": "Reaction removed successfully"}},
    )
    @action(detail=True, methods=["post"])
    def unreact(self, request, pk=None):
        post = self.get_object()
        content_type = ContentType.objects.get_for_model(Post)

        deleted, _ = Reaction.objects.filter(
            user=request.user, content_type=content_type, object_id=post.id
        ).delete()

        if deleted:
            return Response(
                {"detail": "Reaction removed successfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"detail": "No reaction found to remove"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        description="Get all comments for a post with pagination",
        responses={200: CommentSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        post = self.get_object()
        parent_id = request.query_params.get("parent")

        if parent_id:
            queryset = Comment.objects.filter(post=post, parent_id=parent_id)
        else:
            queryset = Comment.objects.filter(post=post, parent__isnull=True)

        queryset = queryset.order_by("-created_at")
        return self._paginated_response(queryset, serializer_class=CommentSerializer)

    @extend_schema(
        description="Add a comment to a post",
        request=CommentSerializer,
        responses={201: CommentSerializer},
    )
    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        post = self.get_object()
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user, post=post)

        if post.author != request.user:
            Notification.objects.create(
                user=post.author,
                notification_type_id=2,
                title=f"{request.user.get_full_name() or request.user.username} commented on your post",
                content=serializer.data["content"][:100],
                is_read=False,
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description="Increment view count for a post",
        responses={200: {"description": "View count incremented"}},
    )
    @action(detail=True, methods=["post"])
    def view(self, request, pk=None):
        post = self.get_object()
        post.views_count = F("views_count") + 1
        post.save(update_fields=["views_count"])
        return Response({"detail": "View count incremented"}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Toggle like for a post. GET returns the current like status and instructions. POST toggles the like.",
        request=LikeToggleSerializer,
        responses={
            200: {"description": "Like status or post unliked"},
            201: {"description": "Post liked"},
        },
    )
    @action(detail=True, methods=["get", "post"], serializer_class=LikeToggleSerializer)
    def like(self, request, pk=None):
        post = self.get_object()
        user = request.user
        content_type = ContentType.objects.get_for_model(post)

        if request.method == "GET":
            liked = Reaction.objects.filter(
                user=user,
                content_type=content_type,
                object_id=post.id,
                reaction_type="like",
            ).exists()
            if liked:
                message = "Post is currently liked. Send a POST request to remove like."
            else:
                message = (
                    "Post is not liked yet. Send a POST request to like this post."
                )
            return Response({"detail": message}, status=status.HTTP_200_OK)

        # POST method: Toggle like using a validated (empty) request body.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        existing_reaction = Reaction.objects.filter(
            user=user,
            content_type=content_type,
            object_id=post.id,
            reaction_type="like",
        ).first()

        if existing_reaction:
            existing_reaction.delete()
            return Response({"message": "Post unliked"}, status=status.HTTP_200_OK)
        else:
            Reaction.objects.create(
                user=user,
                content_type=content_type,
                object_id=post.id,
                reaction_type="like",
            )
            return Response({"message": "Post liked"}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def like_count(self, request, pk=None):
        """
        Returns the number of likes for a post.
        """
        post = self.get_object()
        content_type = ContentType.objects.get_for_model(post)
        count = Reaction.objects.filter(
            user=request.user,  # remove user=request.user if likes are not per user
            content_type=content_type,
            object_id=post.id,
            reaction_type="like",
        ).count()
        return Response({"like_count": count}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def comment_count(self, request, pk=None):
        """
        Returns the number of comments for a post.
        """
        post = self.get_object()
        count = Comment.objects.filter(post=post).count()
        return Response({"comment_count": count}, status=status.HTTP_200_OK)

    def _paginated_response(self, queryset, serializer_class=None):
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = (
                serializer_class(page, many=True, context={"request": self.request})
                if serializer_class
                else self.get_serializer(page, many=True)
            )
            return self.get_paginated_response(serializer.data)

        serializer = (
            serializer_class(queryset, many=True, context={"request": self.request})
            if serializer_class
            else self.get_serializer(queryset, many=True)
        )
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FeedPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        post_id = self.request.query_params.get("post")
        if post_id:
            queryset = queryset.filter(post_id=post_id)

        parent_id = self.request.query_params.get("parent")
        if parent_id:
            if parent_id == "null":
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)

        author_id = self.request.query_params.get("author")
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        return queryset

    def perform_create(self, serializer):
        """Create a new comment"""
        try:
            with transaction.atomic():
                # Set the author to the current user
                comment = serializer.save(author=self.request.user)

                # If this is a root comment on a post, directly create notification here
                # for better performance (avoid signal overhead)
                if not comment.parent and comment.post.author != self.request.user:
                    # Get or create notification type
                    notification_type = NotificationType.objects.get_or_create(
                        id=2,
                        defaults={
                            "name": "post_comment",
                            "description": "Comment on your post",
                            "default_enabled": True,
                            "is_global": True,
                        },
                    )[0]

                    # Create notification with correct field names
                    Notification.objects.create(
                        user=comment.post.author,
                        notification_type=notification_type,
                        title=f"{self.request.user.get_full_name() or self.request.user.username} commented on your post",
                        message=comment.content[
                            :100
                        ],  # Use 'message' instead of 'content'
                        read=False,  # Use 'read' instead of 'is_read'
                    )

                    # Clear cache
                    cache.delete(f"user_notifications_{comment.post.author.id}")

                    # Update post comment count cache
                    cache.set(
                        f"post_{comment.post.id}_comment_count",
                        Comment.objects.filter(post=comment.post, parent=None).count(),
                        timeout=3600,
                    )

        except Exception as e:
            logger.error(f"Error creating comment: {e}", exc_info=True)
            raise serializers.ValidationError({"detail": str(e)})

        post = serializer.validated_data.get("post")
        if post and post.author != self.request.user:
            Notification.objects.create(
                user=post.author,
                notification_type_id=2,
                title=f"{self.request.user.get_full_name() or self.request.user.username} commented on your post",
                message=serializer.validated_data.get("content", "")[
                    :100
                ],  # Changed from 'content' to 'message'
                read=False,  # Changed from 'is_read' to 'read'
            )

        parent = serializer.validated_data.get("parent")
        if parent and parent.author != self.request.user:
            Notification.objects.create(
                user=parent.author,
                notification_type_id=3,
                title=f"{self.request.user.get_full_name() or self.request.user.username} replied to your comment",
                message=serializer.validated_data.get("content", "")[
                    :100
                ],  # Changed from 'content' to 'message'
                read=False,  # Changed from 'is_read' to 'read'
            )

    @extend_schema(
        description="Add a reaction to a comment",
        request=ReactionSerializer,
        responses={201: {"description": "Reaction added successfully"}},
    )
    @action(detail=True, methods=["post"])
    def react(self, request, pk=None):
        comment = self.get_object()
        reaction_type = request.data.get("reaction_type")

        if not reaction_type:
            return Response(
                {"error": "reaction_type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = ContentType.objects.get_for_model(Comment)
        reaction, created = Reaction.objects.update_or_create(
            user=request.user,
            content_type=content_type,
            object_id=comment.id,
            defaults={"reaction_type": reaction_type},
        )

        if comment.author != request.user:
            Notification.objects.create(
                user=comment.author,
                notification_type_id=1,
                title=f"{request.user.get_full_name() or request.user.username} reacted to your comment",
                content=f"{request.user.get_full_name() or request.user.username} reacted with {reaction_type}",
                is_read=False,
            )

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        detail = (
            "Reaction added successfully"
            if created
            else "Reaction updated successfully"
        )
        return Response({"detail": detail}, status=status_code)

    @extend_schema(
        description="Remove user's reaction from a comment",
        responses={200: {"description": "Reaction removed successfully"}},
    )
    @action(detail=True, methods=["post"])
    def unreact(self, request, pk=None):
        comment = self.get_object()
        content_type = ContentType.objects.get_for_model(Comment)

        deleted, _ = Reaction.objects.filter(
            user=request.user, content_type=content_type, object_id=comment.id
        ).delete()

        if deleted:
            return Response(
                {"detail": "Reaction removed successfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"detail": "No reaction found to remove"},
                status=status.HTTP_404_NOT_FOUND,
            )


class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.filter(is_active=True)
    serializer_class = TopicSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "description"]
