# journal/views.py
from rest_framework import viewsets, permissions, filters, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from journal.models import JournalEntry, JournalCategory
from journal.serializers import (
    JournalEntrySerializer,
    JournalEntryDetailSerializer,
    JournalCategorySerializer,
)
from feeds.models import Post
import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List all journal categories for the authenticated user",
        summary="List Journal Categories",
        tags=["Journal Categories"],
    ),
    retrieve=extend_schema(
        description="Retrieve a specific journal category",
        summary="Retrieve Journal Category",
        tags=["Journal Categories"],
    ),
    create=extend_schema(
        description="Create a new journal category",
        summary="Create Journal Category",
        tags=["Journal Categories"],
    ),
    update=extend_schema(
        description="Update a journal category",
        summary="Update Journal Category",
        tags=["Journal Categories"],
    ),
    destroy=extend_schema(
        description="Delete a journal category",
        summary="Delete Journal Category",
        tags=["Journal Categories"],
    ),
)
class JournalCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing journal categories"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = JournalCategorySerializer

    def get_queryset(self):
        """Get categories for the current user"""
        return JournalCategory.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Ensure the user is set when creating a category"""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def entries(self, request, pk=None):
        """Get all entries for a specific category"""
        category = self.get_object()
        entries = JournalEntry.objects.filter(category=category)
        serializer = JournalEntrySerializer(
            entries, many=True, context={"request": request}
        )
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        description="List all journal entries for the authenticated user",
        summary="List Journal Entries",
        tags=["Journal"],
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                description="Filter by start date (YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                description="Filter by end date (YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="shared",
                type=OpenApiTypes.BOOL,
                description="Filter by shared status with therapist",
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                description="Search in title and content",
            ),
            OpenApiParameter(
                name="category",
                type=OpenApiTypes.INT,
                description="Filter by category ID",
            ),
        ],
    )
)
class JournalEntryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing journal entries"""

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "content", "tags"]
    ordering_fields = ["created_at", "updated_at", "word_count"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return different serializers for list, detail, and share views"""
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return JournalEntryDetailSerializer
        elif self.action == "share":
            return serializers.Serializer  # Use a basic serializer for share action
        return JournalEntrySerializer

    def get_queryset(self):
        """Get journal entries for the current user with filtering"""
        queryset = JournalEntry.objects.filter(user=self.request.user)

        # Filter by category
        category_id = self.request.query_params.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Filter by date range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        # Filter by shared status
        shared = self.request.query_params.get("shared")
        if shared is not None:
            queryset = queryset.filter(shared_with_therapist=shared)

        return queryset

    def perform_create(self, serializer):
        """Ensure the user is set when creating a journal entry"""
        # Extract category_id from request data for direct category assignment
        category_id = self.request.data.get("category")
        category = None

        if category_id:
            try:
                # Verify the category belongs to this user
                category = JournalCategory.objects.get(
                    id=category_id, user=self.request.user
                )
            except JournalCategory.DoesNotExist:
                # If category doesn't exist or doesn't belong to user, silently ignore it
                pass

        # Save with the user and validated category
        serializer.save(user=self.request.user, category=category)

    @action(detail=False, methods=["post"], url_path="share/(?P<journal_id>[^/.]+)")
    def share(self, request, journal_id=None):
        """Share a journal entry by its ID and post to feed"""
        try:
            entry = JournalEntry.objects.get(id=journal_id, user=request.user)
            entry.shared_with_therapist = True
            entry.save()

            # Post to feed
            if hasattr(request.user, "patient_profile") and hasattr(
                request.user.patient_profile, "therapist"
            ):
                Post.objects.create(
                    author=request.user,
                    content=f"Shared a journal entry from {entry.created_at.strftime('%Y-%m-%d')}",
                    post_type="text",
                    topics="mental_health",  # Default topic
                    tags="personal_growth",  # Default tag
                )

            return Response(
                {
                    "status": "shared",
                    "message": "Journal entry shared successfully and posted to feed.",
                }
            )
        except JournalEntry.DoesNotExist:
            return Response(
                {"error": "Journal entry not found or not owned by user."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error sharing journal entry: {str(e)}")
            return Response(
                {"error": "An error occurred while sharing the journal entry."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get journal statistics for the current user"""
        entries = self.get_queryset()
        total_entries = entries.count()
        entries_this_month = entries.filter(
            created_at__month=timezone.now().month
        ).count()
        avg_word_count = entries.aggregate(avg_words=Count("word_count"))["avg_words"]

        return Response(
            {
                "total_entries": total_entries,
                "entries_this_month": entries_this_month,
                "average_word_count": avg_word_count,
            }
        )
