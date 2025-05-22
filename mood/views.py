# mood/views.py
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, extend_schema_view
import csv
from django.http import HttpResponse
import logging

from .models import MoodLog
from .serializers import MoodLogSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="List mood logs with optional filtering",
        summary="List Mood Logs",
        tags=["Mood Tracking"],
    ),
    analytics=extend_schema(
        summary="Mood analytics",
        description="Returns mood analytics and trends aggregated data.",
    ),
    export=extend_schema(
        summary="Export mood logs", description="Exports mood logs in CSV format."
    ),
    bulk_create=extend_schema(
        summary="Bulk create mood logs",
        description="Creates multiple mood logs at once.",
    ),
)
class MoodLogViewSet(viewsets.ModelViewSet):
    queryset = MoodLog.objects.all()
    serializer_class = MoodLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["notes"]
    ordering_fields = ["logged_at", "created_at", "mood_rating"]
    filterset_fields = ["logged_at", "created_at", "mood_rating"]
    ordering = ["logged_at"]

    def get_queryset(self):
        queryset = MoodLog.objects.filter(user=self.request.user)

        # Date range filtering
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(logged_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(logged_at__lte=end_date)

        # Mood rating range filtering
        min_rating = self.request.query_params.get("minRating")
        max_rating = self.request.query_params.get("maxRating")
        if min_rating:
            queryset = queryset.filter(mood_rating__gte=min_rating)
        if max_rating:
            queryset = queryset.filter(mood_rating__lte=max_rating)

        # Activities filtering (comma-separated)
        activities = self.request.query_params.get("activities")
        if activities:
            activity_list = [a.strip() for a in activities.split(",") if a.strip()]
            queryset = queryset.filter(activities__in=activity_list)

        # Search text in notes
        search_text = self.request.query_params.get("searchText")
        if search_text:
            queryset = queryset.filter(notes__icontains=search_text)

        return queryset

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """Get mood analytics and trends"""
        queryset = self.get_queryset()
        now = timezone.now()

        # Time ranges for analysis
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # Calculate averages using 'logged_at' and 'mood_rating'
        weekly_avg = (
            queryset.filter(logged_at__gte=week_ago).aggregate(
                avg_mood=Avg("mood_rating")
            )["avg_mood"]
            or 0
        )

        monthly_avg = (
            queryset.filter(logged_at__gte=month_ago).aggregate(
                avg_mood=Avg("mood_rating")
            )["avg_mood"]
            or 0
        )

        # Daily mood averages for the past week
        daily_moods = (
            queryset.filter(logged_at__gte=week_ago)
            .extra(select={"day": "date(logged_at)"})
            .values("day")
            .annotate(avg_mood=Avg("mood_rating"))
            .order_by("day")
        )

        return Response(
            {
                "weekly_average": round(weekly_avg, 2),
                "monthly_average": round(monthly_avg, 2),
                "daily_trends": list(daily_moods),
                "entry_count": queryset.count(),
            }
        )

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Export mood logs to CSV"""
        queryset = self.get_queryset().order_by("logged_at")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="mood_logs.csv"'

        writer = csv.writer(response)
        writer.writerow(["Date", "Mood Score", "Activity"])

        for log in queryset:
            writer.writerow(
                [
                    log.logged_at.strftime("%Y-%m-%d %H:%M:%S"),
                    log.mood_rating,
                    log.activities if log.activities else "",
                ]
            )

        return response

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Create multiple mood logs at once"""
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_bulk_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_bulk_create(self, serializer):
        """Save multiple mood logs with the current user"""
        serializer.save(user=self.request.user)
