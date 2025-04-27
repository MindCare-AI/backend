# journal/views.py
from rest_framework import viewsets, permissions, filters, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from journal.models import JournalEntry
from journal.serializers import JournalEntrySerializer, JournalEntryDetailSerializer
from feeds.models import Post  # Updated from FeedPost to Post
import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all journal entries for the authenticated user",
        summary="List Journal Entries",
        tags=["Journal"],
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                description="Filter by start date (YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                description="Filter by end date (YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name="shared",
                type=OpenApiTypes.BOOL,
                description="Filter by shared status with therapist"
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                description="Search in title and content"
            ),
        ],
    )
)
class JournalEntryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing journal entries"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content', 'tags']
    ordering_fields = ['created_at', 'updated_at', 'word_count']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return different serializers for list, detail, and share views"""
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return JournalEntryDetailSerializer
        elif self.action == 'share':
            return serializers.Serializer  # Use a basic serializer for share action
        return JournalEntrySerializer

    def get_queryset(self):
        """Get journal entries for the current user with filtering"""
        queryset = JournalEntry.objects.filter(user=self.request.user)

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        # Filter by shared status
        shared = self.request.query_params.get('shared')
        if shared is not None:
            queryset = queryset.filter(shared_with_therapist=shared)

        return queryset

    def perform_create(self, serializer):
        """Ensure the user is set when creating a journal entry"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='share/(?P<journal_id>[^/.]+)')
    def share(self, request, journal_id=None):
        """Share a journal entry by its ID and post to feed"""
        try:
            entry = JournalEntry.objects.get(id=journal_id, user=request.user)
            entry.shared_with_therapist = True
            entry.save()

            # Post to feed
            if hasattr(request.user, 'patient_profile') and hasattr(request.user.patient_profile, 'therapist'):
                Post.objects.create(
                    author=request.user,
                    content=f"Shared a journal entry: {entry.title}",
                    post_type='text',
                    topics='mental_health',  # Default topic
                    tags='personal_growth'   # Default tag
                )

            return Response({'status': 'shared', 'message': 'Journal entry shared successfully and posted to feed.'})
        except JournalEntry.DoesNotExist:
            return Response({'error': 'Journal entry not found or not owned by user.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error sharing journal entry: {str(e)}")
            return Response({'error': 'An error occurred while sharing the journal entry.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get journal statistics for the current user"""
        entries = self.get_queryset()
        total_entries = entries.count()
        entries_this_month = entries.filter(
            created_at__month=timezone.now().month
        ).count()
        avg_word_count = entries.aggregate(avg_words=Count('word_count'))['avg_words']
        
        return Response({
            'total_entries': total_entries,
            'entries_this_month': entries_this_month,
            'average_word_count': avg_word_count,
        })
