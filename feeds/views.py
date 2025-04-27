from django.db.models import F, Q, Count
from django.contrib.contenttypes.models import ContentType
from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from users.models import CustomUser
from feeds.models import (
    Post, 
    Comment, 
    Topic, 
    Reaction, 
    SavedPost, 
    HiddenPost, 
    PollOption, 
    PollVote
)
from feeds.serializers import (
    PostSerializer, 
    PostDetailSerializer,
    CommentSerializer, 
    TopicSerializer, 
    ReactionSerializer,
    SavedPostSerializer,
    PollOptionSerializer,
    PollVoteSerializer,
    UserProfileMinimalSerializer
)

from notifications.models import Notification

import logging

logger = logging.getLogger(__name__)


class FeedPagination(PageNumberPagination):
    """Pagination for feed posts with customizable page size"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class TopicViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Topics"""
    queryset = Topic.objects.filter(is_active=True)
    serializer_class = TopicSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']


class PostViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Posts"""
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['content', 'tags']
    ordering_fields = ['created_at', 'updated_at', 'views_count']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == 'retrieve':
            return PostDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """
        Get filtered queryset based on visibility rules and user preferences
        """
        user = self.request.user
        
        # Start with posts the user should be able to see based on visibility
        base_queryset = Post.objects.filter(
            Q(visibility='public') | 
            Q(author=user) |
            (Q(visibility='patients') & Q(author__user_type='therapist') & Q(user__user_type='patient')) |
            (Q(visibility='therapists') & Q(author__user_type='patient') & Q(user__user_type='therapist')) |
            (Q(visibility='connections') & Q(author__connections=user))
        ).exclude(
            is_archived=True
        ).exclude(
            id__in=HiddenPost.objects.filter(user=user).values_list('post_id', flat=True)
        )
        
        # Apply additional filters from query parameters
        queryset = self._apply_filters(base_queryset)
        
        return queryset.select_related('author').prefetch_related('topics', 'media_files')

    def _apply_filters(self, queryset):
        """Apply various filters from query parameters"""
        # Filter by topic
        topic_id = self.request.query_params.get('topic')
        if topic_id:
            queryset = queryset.filter(topics__id=topic_id)
            
        # Filter by author/user profile
        author_id = self.request.query_params.get('author')
        if author_id:
            queryset = queryset.filter(author_id=author_id)
            
        # Filter by post type
        post_type = self.request.query_params.get('post_type')
        if post_type:
            queryset = queryset.filter(post_type=post_type)
            
        # Filter by tags
        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
            
        # Filter for polls only
        polls_only = self.request.query_params.get('polls_only')
        if polls_only and polls_only.lower() == 'true':
            queryset = queryset.filter(post_type='poll')
            
        # Filter for featured posts
        featured = self.request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            queryset = queryset.filter(is_featured=True)

        # Filter for minimum reactions count
        min_reactions = self.request.query_params.get('min_reactions')
        if min_reactions and min_reactions.isdigit():
            queryset = queryset.annotate(total_reactions=Count('reactions')).filter(total_reactions__gte=int(min_reactions))
            
        return queryset
    
    def perform_create(self, serializer):
        """Create a post and associate with authenticated user"""
        serializer.save(author=self.request.user)
        
    @extend_schema(
        description="Retrieve the user's personalized feed with posts from connections and relevant content",
        responses={200: PostSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def my_feed(self, request):
        """
        Get personalized feed for the current user (from connections & followed topics)
        """
        user = request.user
        
        # Get posts from user's connections and followed topics with higher weight
        # Also include posts the user has interacted with
        queryset = Post.objects.filter(
            Q(visibility='public') | 
            Q(author=user) |
            (Q(visibility='patients') & Q(author__user_type='therapist') & Q(user__user_type='patient')) |
            (Q(visibility='therapists') & Q(author__user_type='patient') & Q(user__user_type='therapist')) |
            (Q(visibility='connections') & Q(author__connections=user))
        ).exclude(
            is_archived=True
        ).exclude(
            id__in=HiddenPost.objects.filter(user=user).values_list('post_id', flat=True)
        ).order_by('-created_at')
        
        return self._paginated_response(queryset)

    @extend_schema(
        description="List posts that the user has saved",
        responses={200: PostSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def saved(self, request):
        """Get posts saved by the current user"""
        saved_post_ids = SavedPost.objects.filter(
            user=request.user
        ).values_list('post_id', flat=True)
        
        queryset = Post.objects.filter(
            id__in=saved_post_ids
        ).order_by('-created_at')
        
        return self._paginated_response(queryset)

    @extend_schema(
        description="Save a post to the user's saved collection",
        responses={201: {"description": "Post saved successfully"}},
    )
    @action(detail=True, methods=['post'])
    def save(self, request, pk=None):
        """Save a post for the current user"""
        post = self.get_object()
        saved_post, created = SavedPost.objects.get_or_create(
            user=request.user,
            post=post
        )
        
        if created:
            return Response(
                {'detail': 'Post saved successfully'}, 
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {'detail': 'Post was already saved'}, 
                status=status.HTTP_200_OK
            )

    @extend_schema(
        description="Remove a post from the user's saved collection",
        responses={200: {"description": "Post removed from saved"}},
    )
    @action(detail=True, methods=['post'])
    def unsave(self, request, pk=None):
        """Remove a post from saved collection"""
        post = self.get_object()
        deleted, _ = SavedPost.objects.filter(
            user=request.user,
            post=post
        ).delete()
        
        if deleted:
            return Response(
                {'detail': 'Post removed from saved'}, 
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'detail': 'Post was not in your saved collection'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        description="Add a reaction to a post",
        request={
            "type": "object",
            "properties": {
                "reaction_type": {"type": "string", "enum": ["like", "love", "support", "insightful", "celebrate"]}
            },
            "required": ["reaction_type"]
        },
        responses={201: {"description": "Reaction added successfully"}},
    )
    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """Add a reaction to a post"""
        post = self.get_object()
        reaction_type = request.data.get('reaction_type')
        
        if not reaction_type:
            return Response(
                {'error': 'reaction_type is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        content_type = ContentType.objects.get_for_model(Post)
        
        reaction, created = Reaction.objects.update_or_create(
            user=request.user,
            content_type=content_type,
            object_id=post.id,
            defaults={'reaction_type': reaction_type}
        )
        
        # Create notification for the post author if it's not their own post
        if post.author != request.user:
            Notification.objects.create(
                user=post.author,
                notification_type_id=1,  # Assuming notification_type 1 is for reactions
                title=f"{request.user.get_full_name() or request.user.username} reacted to your post",
                content=f"{request.user.get_full_name() or request.user.username} reacted with {reaction_type}",
                is_read=False
            )
        
        if created:
            status_code = status.HTTP_201_CREATED
            detail = 'Reaction added successfully'
        else:
            status_code = status.HTTP_200_OK
            detail = 'Reaction updated successfully'
            
        return Response({'detail': detail}, status=status_code)

    @extend_schema(
        description="Remove user's reaction from a post",
        responses={200: {"description": "Reaction removed successfully"}},
    )
    @action(detail=True, methods=['post'])
    def unreact(self, request, pk=None):
        """Remove reaction from a post"""
        post = self.get_object()
        content_type = ContentType.objects.get_for_model(Post)
        
        deleted, _ = Reaction.objects.filter(
            user=request.user,
            content_type=content_type,
            object_id=post.id
        ).delete()
        
        if deleted:
            return Response(
                {'detail': 'Reaction removed successfully'}, 
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'detail': 'No reaction found to remove'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        description="Get all comments for a post with pagination",
        responses={200: CommentSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """Get all comments for a post"""
        post = self.get_object()
        
        # Get parent comments by default, unless 'parent' query param is specified
        parent_id = request.query_params.get('parent')
        
        if parent_id:
            # If parent_id is specified, get replies to that comment
            queryset = Comment.objects.filter(post=post, parent_id=parent_id)
        else:
            # Otherwise get top-level comments
            queryset = Comment.objects.filter(post=post, parent__isnull=True)
            
        queryset = queryset.order_by('-created_at')
        
        return self._paginated_response(
            queryset, 
            serializer_class=CommentSerializer
        )

    @extend_schema(
        description="Add a comment to a post",
        request=CommentSerializer,
        responses={201: CommentSerializer},
    )
    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        """Add a comment to a post"""
        post = self.get_object()
        
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        serializer.save(
            author=request.user,
            post=post
        )
        
        # Create notification for the post author if it's not their own comment
        if post.author != request.user:
            Notification.objects.create(
                user=post.author,
                notification_type_id=2,  # Assuming notification_type 2 is for comments
                title=f"{request.user.get_full_name() or request.user.username} commented on your post",
                content=serializer.data['content'][:100],
                is_read=False
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description="Vote on a poll option",
        request={
            "type": "object",
            "properties": {
                "poll_option_id": {"type": "integer"}
            },
            "required": ["poll_option_id"]
        },
        responses={201: {"description": "Vote recorded successfully"}},
    )
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Vote on a poll"""
        post = self.get_object()
        poll_option_id = request.data.get('poll_option_id')
        
        if post.post_type != 'poll':
            return Response(
                {'error': 'This post is not a poll'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if not poll_option_id:
            return Response(
                {'error': 'poll_option_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            poll_option = PollOption.objects.get(id=poll_option_id, post=post)
        except PollOption.DoesNotExist:
            return Response(
                {'error': 'Invalid poll option'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Check if user already voted
        existing_vote = PollVote.objects.filter(
            poll_option__post=post,
            user=request.user
        ).first()
        
        if existing_vote:
            return Response(
                {'error': 'You have already voted on this poll'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Create the vote
        PollVote.objects.create(
            poll_option=poll_option,
            user=request.user
        )
        
        return Response(
            {'detail': 'Vote recorded successfully'}, 
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        description="Hide a post from user's feed",
        responses={200: {"description": "Post hidden successfully"}},
    )
    @action(detail=True, methods=['post'])
    def hide(self, request, pk=None):
        """Hide a post from feed"""
        post = self.get_object()
        reason = request.data.get('reason', '')
        
        hidden_post, created = HiddenPost.objects.get_or_create(
            user=request.user,
            post=post,
            defaults={'reason': reason}
        )
        
        if created:
            return Response(
                {'detail': 'Post hidden successfully'}, 
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {'detail': 'Post was already hidden'}, 
                status=status.HTTP_200_OK
            )

    @extend_schema(
        description="Increment view count for a post",
        responses={200: {"description": "View count incremented"}},
    )
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Increment view count for a post"""
        post = self.get_object()
        post.views_count = F('views_count') + 1
        post.save(update_fields=['views_count'])
        
        return Response(
            {'detail': 'View count incremented'}, 
            status=status.HTTP_200_OK
        )
        
    def _paginated_response(self, queryset, serializer_class=None):
        """Helper method to return paginated response"""
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_class(page, many=True, context={'request': self.request}) if serializer_class else self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = serializer_class(queryset, many=True, context={'request': self.request}) if serializer_class else self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Comments"""
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FeedPagination
    
    def get_queryset(self):
        """Filter comments based on parameters"""
        queryset = super().get_queryset()
        
        # Filter by post
        post_id = self.request.query_params.get('post')
        if post_id:
            queryset = queryset.filter(post_id=post_id)
            
        # Filter by parent (for replies)
        parent_id = self.request.query_params.get('parent')
        if parent_id:
            if parent_id == 'null':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)
                
        # Filter by author
        author_id = self.request.query_params.get('author')
        if author_id:
            queryset = queryset.filter(author_id=author_id)
            
        return queryset
    
    def perform_create(self, serializer):
        """Create a comment and associate with authenticated user"""
        serializer.save(author=self.request.user)
        
        # Create notification for the post author if it's not their own comment
        post = serializer.validated_data.get('post')
        if post and post.author != self.request.user:
            Notification.objects.create(
                user=post.author,
                notification_type_id=2,  # Assuming notification_type 2 is for comments
                title=f"{self.request.user.get_full_name() or self.request.user.username} commented on your post",
                content=serializer.validated_data.get('content', '')[:100],
                is_read=False
            )
            
        # Create notification for parent comment author if this is a reply
        parent = serializer.validated_data.get('parent')
        if parent and parent.author != self.request.user:
            Notification.objects.create(
                user=parent.author,
                notification_type_id=3,  # Assuming notification_type 3 is for replies
                title=f"{self.request.user.get_full_name() or self.request.user.username} replied to your comment",
                content=serializer.validated_data.get('content', '')[:100],
                is_read=False
            )
    
    @extend_schema(
        description="Add a reaction to a comment",
        request={
            "type": "object",
            "properties": {
                "reaction_type": {"type": "string", "enum": ["like", "love", "support", "insightful", "celebrate"]}
            },
            "required": ["reaction_type"]
        },
        responses={201: {"description": "Reaction added successfully"}},
    )
    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """Add a reaction to a comment"""
        comment = self.get_object()
        reaction_type = request.data.get('reaction_type')
        
        if not reaction_type:
            return Response(
                {'error': 'reaction_type is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        content_type = ContentType.objects.get_for_model(Comment)
        
        reaction, created = Reaction.objects.update_or_create(
            user=request.user,
            content_type=content_type,
            object_id=comment.id,
            defaults={'reaction_type': reaction_type}
        )
        
        # Create notification for the comment author if it's not their own reaction
        if comment.author != request.user:
            Notification.objects.create(
                user=comment.author,
                notification_type_id=1,  # Assuming notification_type 1 is for reactions
                title=f"{request.user.get_full_name() or request.user.username} reacted to your comment",
                content=f"{request.user.get_full_name() or request.user.username} reacted with {reaction_type}",
                is_read=False
            )
        
        if created:
            status_code = status.HTTP_201_CREATED
            detail = 'Reaction added successfully'
        else:
            status_code = status.HTTP_200_OK
            detail = 'Reaction updated successfully'
            
        return Response({'detail': detail}, status=status_code)

    @extend_schema(
        description="Remove user's reaction from a comment",
        responses={200: {"description": "Reaction removed successfully"}},
    )
    @action(detail=True, methods=['post'])
    def unreact(self, request, pk=None):
        """Remove reaction from a comment"""
        comment = self.get_object()
        content_type = ContentType.objects.get_for_model(Comment)
        
        deleted, _ = Reaction.objects.filter(
            user=request.user,
            content_type=content_type,
            object_id=comment.id
        ).delete()
        
        if deleted:
            return Response(
                {'detail': 'Reaction removed successfully'}, 
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'detail': 'No reaction found to remove'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class SearchViewSet(viewsets.ViewSet):
    """ViewSet for search functionality across posts, topics and users"""
    permission_classes = [IsAuthenticated]
    pagination_class = FeedPagination
    
    @extend_schema(
        description="Search posts, topics, and users",
        parameters=[
            OpenApiParameter(
                name="q", 
                type=OpenApiTypes.STR, 
                description="Search query"
            ),
            OpenApiParameter(
                name="type", 
                type=OpenApiTypes.STR, 
                description="Type of results to return (posts, topics, users, or all)"
            ),
        ],
        responses={200: {"description": "Search results"}},
    )
    def list(self, request):
        """Search posts, topics, and users"""
        query = request.query_params.get('q', '')
        search_type = request.query_params.get('type', 'all')
        
        if not query:
            return Response(
                {'error': 'Search query is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        results = {}
        
        # Search posts
        if search_type in ['all', 'posts']:
            posts = Post.objects.filter(
                Q(content__icontains=query) | 
                Q(tags__contains=[query])
            ).order_by('-created_at')
            
            paginator = FeedPagination()
            page = paginator.paginate_queryset(posts, request)
            serializer = PostSerializer(page, many=True, context={'request': request})
            
            results['posts'] = {
                'count': posts.count(),
                'results': serializer.data
            }
            
        # Search topics
        if search_type in ['all', 'topics']:
            topics = Topic.objects.filter(
                Q(name__icontains=query) | 
                Q(description__icontains=query)
            )
            serializer = TopicSerializer(topics, many=True)
            results['topics'] = {
                'count': topics.count(),
                'results': serializer.data
            }
            
        # Search users
        if search_type in ['all', 'users']:
            users = CustomUser.objects.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query)
            )
            serializer = UserProfileMinimalSerializer(users, many=True)
            results['users'] = {
                'count': users.count(),
                'results': serializer.data
            }
            
        return Response(results)


class UserProfileViewSet(viewsets.ViewSet):
    """ViewSet for user profile information related to feeds"""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        description="Get profile information for a user",
        responses={200: UserProfileMinimalSerializer},
    )
    def retrieve(self, request, pk=None):
        """Get user profile information"""
        try:
            user = CustomUser.objects.get(pk=pk)
            serializer = UserProfileMinimalSerializer(user)
            
            # Get additional feed-related stats
            post_count = Post.objects.filter(author=user).count()
            comment_count = Comment.objects.filter(author=user).count()
            
            data = serializer.data
            data['stats'] = {
                'post_count': post_count,
                'comment_count': comment_count
            }
            
            return Response(data)
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        description="Get posts by a specific user",
        responses={200: PostSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def posts(self, request, pk=None):
        """Get posts created by a user"""
        try:
            user = CustomUser.objects.get(pk=pk)
            
            # Filter posts based on visibility rules
            current_user = request.user
            
            if current_user == user:
                # User can see all their own posts
                posts = Post.objects.filter(author=user)
            else:
                # Apply visibility rules
                posts = Post.objects.filter(
                    Q(author=user) &
                    (Q(visibility='public') |
                     (Q(visibility='patients') & Q(current_user__user_type='patient')) |
                     (Q(visibility='therapists') & Q(current_user__user_type='therapist')) |
                     (Q(visibility='connections') & Q(author__connections=current_user)))
                ).exclude(is_archived=True)
                
            posts = posts.order_by('-created_at')
            
            # Paginate results
            paginator = FeedPagination()
            page = paginator.paginate_queryset(posts, request)
            
            serializer = PostSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
            
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
