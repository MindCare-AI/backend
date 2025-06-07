# datawarehouse/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Avg, Q, Sum
import logging

# Service imports
from .services.realtime_analytics import realtime_service
from .services.audit_trail import audit_service
from .services.security_service import security_service
from .services.backup_recovery import backup_service



from .models import (
    DataCollectionRun,
    UserDataSnapshot,
    MoodTrendAnalysis,
    JournalInsightCache,
    CommunicationMetrics,
    FeatureUsageMetrics,
    PredictiveModel,
    DataQualityReport,
)
from .serializers import (
    DataCollectionRunSerializer,
    UserDataSnapshotSerializer,
    MoodTrendAnalysisSerializer,
    JournalInsightCacheSerializer,
    CommunicationMetricsSerializer,
    FeatureUsageMetricsSerializer,
    PredictiveModelSerializer,
    DataQualityReportSerializer,
    UnifiedDataSnapshotSerializer,
)
from .services.unified_data_collection_service import UnifiedDataCollectionService

logger = logging.getLogger(__name__)

User = get_user_model()
class DataCollectionRunViewSet(viewsets.ModelViewSet):
    """ViewSet for managing data collection runs"""

    queryset = DataCollectionRun.objects.all()
    serializer_class = DataCollectionRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by run type if specified
        run_type = self.request.query_params.get("run_type")
        if run_type:
            queryset = queryset.filter(run_type=run_type)

        # Filter by status if specified
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by date range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(started_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(started_at__lte=end_date)

        return queryset

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get summary statistics for data collection runs"""
        queryset = self.get_queryset()

        total_runs = queryset.count()
        successful_runs = queryset.filter(status="completed").count()
        failed_runs = queryset.filter(status="failed").count()
        running_runs = queryset.filter(status="running").count()

        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

        avg_processing_time = (
            queryset.filter(completed_at__isnull=False)
            .extra(
                select={"duration": "EXTRACT(EPOCH FROM (completed_at - started_at))"}
            )
            .aggregate(avg_duration=Avg("duration"))["avg_duration"]
        )

        return Response(
            {
                "total_runs": total_runs,
                "successful_runs": successful_runs,
                "failed_runs": failed_runs,
                "running_runs": running_runs,
                "success_rate": round(success_rate, 2),
                "avg_processing_time_seconds": avg_processing_time,
            }
        )

    @action(detail=False, methods=['post'])
    def trigger_collection(self, request):
        """Trigger a new data collection run"""
        try:
            from .services.etl_service import etl_service
            job = etl_service.run_full_etl()
            return Response({'job_id': job.job_id, 'status': job.status})
        except Exception as e:
            logger.error(f"Error triggering collection: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserDataSnapshotViewSet(viewsets.ModelViewSet):
    """ViewSet for user data snapshots"""

    queryset = UserDataSnapshot.objects.all()
    serializer_class = UserDataSnapshotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by user if specified
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by date range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(snapshot_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(snapshot_date__lte=end_date)

        # Filter by risk level
        risk_level = self.request.query_params.get("risk_level")
        if risk_level == "high":
            queryset = queryset.filter(needs_attention=True)
        elif risk_level == "low":
            queryset = queryset.filter(needs_attention=False)

        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)

        return queryset

    @action(detail=False, methods=["get"])
    def user_trends(self, request):
        """Get user trend analysis"""
        user_id = request.query_params.get("user_id")
        days = int(request.query_params.get("days", 30))

        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        snapshots = UserDataSnapshot.objects.filter(
            user_id=user_id, snapshot_date__gte=start_date, snapshot_date__lte=end_date
        ).order_by("snapshot_date")

        serializer = self.get_serializer(snapshots, many=True)
        return Response(
            {
                "user_id": user_id,
                "period": f"{days} days",
                "data_points": len(snapshots),
                "snapshots": serializer.data,
            }
        )

    @action(detail=False, methods=["get"])
    def risk_dashboard(self, request):
        """Get risk dashboard data"""
        queryset = self.get_queryset()

        high_risk_users = (
            queryset.filter(needs_attention=True).values("user").distinct().count()
        )
        total_users = queryset.values("user").distinct().count()

        avg_risk_score = queryset.aggregate(avg_risk=Avg("risk_score"))["avg_risk"]

        risk_distribution = queryset.aggregate(
            low_risk=Count("id", filter=Q(risk_score__lt=0.3)),
            medium_risk=Count("id", filter=Q(risk_score__gte=0.3, risk_score__lt=0.7)),
            high_risk=Count("id", filter=Q(risk_score__gte=0.7)),
        )

        return Response(
            {
                "high_risk_users": high_risk_users,
                "total_users": total_users,
                "avg_risk_score": round(avg_risk_score, 3) if avg_risk_score else 0,
                "risk_distribution": risk_distribution,
            }
        )


class MoodTrendAnalysisViewSet(viewsets.ModelViewSet):
    """ViewSet for mood trend analysis"""

    queryset = MoodTrendAnalysis.objects.all()
    serializer_class = MoodTrendAnalysisSerializer
    permission_classes = [IsAuthenticated]  # Restored authentication

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by user if specified
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by analysis type
        analysis_type = self.request.query_params.get("analysis_type")
        if analysis_type:
            queryset = queryset.filter(analysis_type=analysis_type)

        return queryset


class JournalInsightCacheViewSet(viewsets.ModelViewSet):
    """ViewSet for journal insight cache"""

    queryset = JournalInsightCache.objects.all()
    serializer_class = JournalInsightCacheSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by user if specified
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter expired cache entries
        include_expired = self.request.query_params.get("include_expired", "false")
        if include_expired.lower() != "true":
            queryset = queryset.filter(expires_at__gt=timezone.now())

        return queryset


class CommunicationMetricsViewSet(viewsets.ModelViewSet):
    """ViewSet for communication metrics"""

    queryset = CommunicationMetrics.objects.all()
    serializer_class = CommunicationMetricsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by user if specified
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset


class FeatureUsageMetricsViewSet(viewsets.ModelViewSet):
    """ViewSet for feature usage metrics"""

    queryset = FeatureUsageMetrics.objects.all()
    serializer_class = FeatureUsageMetricsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by user if specified
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by date range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    @action(detail=False, methods=["get"])
    def engagement_stats(self, request):
        """Get engagement statistics"""
        user_id = request.query_params.get("user_id")
        days = int(request.query_params.get("days", 30))

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        queryset = self.get_queryset().filter(date__gte=start_date, date__lte=end_date)

        if user_id:
            queryset = queryset.filter(user_id=user_id)

        total_sessions = queryset.aggregate(total=Sum("session_count"))["total"] or 0
        total_time = (
            queryset.aggregate(total=Sum("total_time_spent_minutes"))["total"] or 0
        )
        avg_engagement = queryset.aggregate(avg=Avg("engagement_score"))["avg"] or 0

        return Response(
            {
                "period_days": days,
                "total_sessions": total_sessions,
                "total_time_minutes": total_time,
                "avg_engagement_score": round(avg_engagement, 2),
                "unique_users": queryset.values("user").distinct().count(),
            }
        )


class PredictiveModelViewSet(viewsets.ModelViewSet):
    """ViewSet for predictive models"""

    queryset = PredictiveModel.objects.all()
    serializer_class = PredictiveModelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by model type
        model_type = self.request.query_params.get("model_type")
        if model_type:
            queryset = queryset.filter(model_type=model_type)

        # Filter by active status
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset

    @action(detail=False, methods=["get"])
    def performance_comparison(self, request):
        """Compare performance across models"""
        model_type = request.query_params.get("model_type")

        queryset = self.get_queryset()
        if model_type:
            queryset = queryset.filter(model_type=model_type)

        models_performance = []
        for model in queryset:
            models_performance.append(
                {
                    "name": model.name,
                    "version": model.version,
                    "accuracy": model.accuracy,
                    "f1_score": model.f1_score,
                    "is_active": model.is_active,
                    "training_date": model.training_date,
                }
            )

        return Response({"model_type": model_type, "models": models_performance})


class DataQualityReportViewSet(viewsets.ModelViewSet):
    """ViewSet for data quality reports"""

    queryset = DataQualityReport.objects.all()
    serializer_class = DataQualityReportSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def latest_report(self, request):
        """Get the latest data quality report"""
        latest_report = self.get_queryset().first()
        if latest_report:
            serializer = self.get_serializer(latest_report)
            return Response(serializer.data)
        return Response({"message": "No data quality reports available"})


class UnifiedDataCollectionViewSet(viewsets.ViewSet):
    """ViewSet for unified data collection operations"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List recent unified data collections"""
        try:
            # Get recent user data snapshots with summary information
            days = int(request.query_params.get("days", 7))
            user_id = request.query_params.get("user_id")

            # Base queryset
            queryset = UserDataSnapshot.objects.all()

            # Filter by user if specified
            if user_id:
                queryset = queryset.filter(user_id=user_id)

            # Filter by recent data
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            queryset = queryset.filter(
                snapshot_date__gte=start_date, snapshot_date__lte=end_date
            ).order_by("-snapshot_date")

            # Calculate summary data before slicing
            total_count = queryset.count()
            summary_data = {
                "total_users": queryset.values("user_id").distinct().count(),
                "avg_mood_score": queryset.aggregate(avg=Avg("avg_mood_score"))["avg"],
                "total_mood_entries": queryset.aggregate(
                    total=Sum("mood_entries_count")
                )["total"]
                or 0,
                "total_journal_entries": queryset.aggregate(
                    total=Sum("journal_entries_count")
                )["total"]
                or 0,
            }

            # Limit results for performance (after calculating summary)
            limited_queryset = queryset[:100]

            # Serialize the data
            serializer = UserDataSnapshotSerializer(limited_queryset, many=True)

            # Add summary metadata
            response_data = {
                "count": total_count,
                "period_days": days,
                "results": serializer.data,
                "summary": summary_data,
            }

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error listing unified data collections: {str(e)}")
            return Response(
                {"error": f"Failed to list collections: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request):
        """Create a new unified data collection for a user"""
        try:
            user_id = request.data.get("user_id")
            days = int(request.data.get("days", 30))
            force_refresh = request.data.get("force_refresh", False)

            if not user_id:
                return Response(
                    {"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Verify user exists
            if not User.objects.filter(id=user_id).exists():
                return Response(
                    {"error": f"User with id {user_id} does not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Create unified data collector
            unified_collector = UnifiedDataCollectionService()

            # Collect unified data
            unified_snapshot = unified_collector.collect_unified_data(
                user_id, days, force_refresh
            )

            # Serialize the response
            serializer = UnifiedDataSnapshotSerializer(unified_snapshot)

            return Response(
                {
                    "message": f"Successfully collected unified data for user {user_id}",
                    "data": serializer.data,
                    "collection_metadata": {
                        "user_id": user_id,
                        "period_days": days,
                        "force_refresh": force_refresh,
                        "collected_at": timezone.now().isoformat(),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Error creating unified data collection: {str(e)}")
            return Response(
                {"error": f"Failed to create collection: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, pk=None):
        """Retrieve a specific unified data collection"""
        try:
            # Get the snapshot by ID
            snapshot = UserDataSnapshot.objects.get(id=pk)

            # Serialize the response
            serializer = UserDataSnapshotSerializer(snapshot)

            return Response(
                {
                    "data": serializer.data,
                    "metadata": {
                        "snapshot_id": pk,
                        "retrieved_at": timezone.now().isoformat(),
                    },
                }
            )

        except UserDataSnapshot.DoesNotExist:
            return Response(
                {"error": f"Unified data collection with id {pk} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error retrieving unified data collection {pk}: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve collection: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def collect_data(self, request):
        """Trigger unified data collection (custom action for backward compatibility)"""
        return self.create(request)


class DatawarehouseHealthView(viewsets.ViewSet):
    """Health check endpoint for datawarehouse services"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Get health status of all datawarehouse services"""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": timezone.now(),
                "services": {
                    "database": self._check_database_health(),
                    "data_collection": self._check_data_collection_health(),
                    "unified_collection": self._check_unified_collection_health(),
                    "cache": self._check_cache_health(),
                },
                "summary": {
                    "total_services": 4,
                    "healthy_services": 0,
                    "unhealthy_services": 0,
                },
            }

            # Count healthy services
            for service_name, service_health in health_status["services"].items():
                if service_health["status"] == "healthy":
                    health_status["summary"]["healthy_services"] += 1
                else:
                    health_status["summary"]["unhealthy_services"] += 1

            # Overall status
            if health_status["summary"]["unhealthy_services"] > 0:
                health_status["status"] = (
                    "degraded"
                    if health_status["summary"]["healthy_services"] > 0
                    else "unhealthy"
                )

            return Response(health_status)

        except Exception as e:
            logger.error(f"Error checking datawarehouse health: {str(e)}")
            return Response(
                {"status": "unhealthy", "error": str(e), "timestamp": timezone.now()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _check_database_health(self):
        """Check database connectivity and basic operations"""
        try:
            # Test database connection with a simple query
            count = UserDataSnapshot.objects.count()
            return {
                "status": "healthy",
                "details": f"{count} user snapshots in database",
                "last_checked": timezone.now(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_checked": timezone.now(),
            }

    def _check_data_collection_health(self):
        """Check data collection service health"""
        try:
            # Check recent collection runs
            recent_runs = DataCollectionRun.objects.filter(
                started_at__gte=timezone.now() - timedelta(hours=24)
            )

            successful_runs = recent_runs.filter(status="completed").count()
            total_runs = recent_runs.count()

            if total_runs == 0:
                status_text = "no_recent_activity"
            elif successful_runs / total_runs >= 0.8:
                status_text = "healthy"
            else:
                status_text = "degraded"

            return {
                "status": status_text,
                "details": f"{successful_runs}/{total_runs} successful runs in last 24h",
                "last_checked": timezone.now(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_checked": timezone.now(),
            }

    def _check_unified_collection_health(self):
        """Check unified data collection service health"""
        try:
            # Try to initialize the service to check if it's accessible
            UnifiedDataCollectionService()

            return {
                "status": "healthy",
                "details": "Unified collection service accessible",
                "last_checked": timezone.now(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_checked": timezone.now(),
            }

    def _check_cache_health(self):
        """Check cache service health"""
        try:
            # Check if journal insights cache is working
            cache_count = JournalInsightCache.objects.filter(
                expires_at__gt=timezone.now()
            ).count()

            return {
                "status": "healthy",
                "details": f"{cache_count} active cache entries",
                "last_checked": timezone.now(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_checked": timezone.now(),
            }


class DatawarehouseDashboardView(viewsets.ViewSet):
    """Dashboard view providing overview statistics"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Get dashboard overview data"""
        try:
            # Get time range from query params
            days = int(request.query_params.get("days", 7))
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)

            dashboard_data = {
                "period": f"{days} days",
                "generated_at": timezone.now(),
                "overview": self._get_overview_stats(),
                "data_collection": self._get_collection_stats(start_date, end_date),
                "user_engagement": self._get_engagement_stats(start_date, end_date),
                "data_quality": self._get_quality_stats(),
                "risk_assessment": self._get_risk_stats(),
                "trending": self._get_trending_stats(start_date, end_date),
            }

            return Response(dashboard_data)

        except Exception as e:
            logger.error(f"Error generating dashboard data: {str(e)}")
            return Response(
                {"error": f"Failed to generate dashboard: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_overview_stats(self):
        """Get high-level overview statistics"""
        total_users = User.objects.count()
        active_users = (
            UserDataSnapshot.objects.filter(
                snapshot_date__gte=timezone.now().date() - timedelta(days=7)
            )
            .values("user")
            .distinct()
            .count()
        )

        total_snapshots = UserDataSnapshot.objects.count()
        total_models = PredictiveModel.objects.filter(is_active=True).count()

        return {
            "total_users": total_users,
            "active_users_7d": active_users,
            "total_data_snapshots": total_snapshots,
            "active_ml_models": total_models,
        }

    def _get_collection_stats(self, start_date, end_date):
        """Get data collection statistics"""
        runs = DataCollectionRun.objects.filter(
            started_at__date__gte=start_date, started_at__date__lte=end_date
        )

        total_runs = runs.count()
        successful_runs = runs.filter(status="completed").count()
        failed_runs = runs.filter(status="failed").count()

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate": round((successful_runs / total_runs * 100), 2)
            if total_runs > 0
            else 0,
        }

    def _get_engagement_stats(self, start_date, end_date):
        """Get user engagement statistics"""
        snapshots = UserDataSnapshot.objects.filter(
            snapshot_date__gte=start_date, snapshot_date__lte=end_date
        )

        total_mood_entries = (
            snapshots.aggregate(total=Sum("mood_entries_count"))["total"] or 0
        )
        total_journal_entries = (
            snapshots.aggregate(total=Sum("journal_entries_count"))["total"] or 0
        )
        total_messages = snapshots.aggregate(total=Sum("messages_sent"))["total"] or 0

        avg_engagement = (
            snapshots.aggregate(avg=Avg("social_engagement_score"))["avg"] or 0
        )

        return {
            "mood_entries": total_mood_entries,
            "journal_entries": total_journal_entries,
            "messages_sent": total_messages,
            "avg_engagement_score": round(avg_engagement, 2),
        }

    def _get_quality_stats(self):
        """Get data quality statistics"""
        latest_report = DataQualityReport.objects.first()

        if latest_report:
            return {
                "completeness_score": latest_report.data_completeness_score,
                "critical_issues": len(latest_report.critical_issues),
                "warnings": len(latest_report.warnings),
                "last_report_date": latest_report.report_date,
            }
        else:
            return {
                "completeness_score": 0,
                "critical_issues": 0,
                "warnings": 0,
                "last_report_date": None,
            }

    def _get_risk_stats(self):
        """Get risk assessment statistics"""
        latest_snapshots = UserDataSnapshot.objects.filter(
            snapshot_date__gte=timezone.now().date() - timedelta(days=1)
        )

        high_risk_users = latest_snapshots.filter(needs_attention=True).count()
        total_users = latest_snapshots.values("user").distinct().count()

        avg_risk_score = latest_snapshots.aggregate(avg=Avg("risk_score"))["avg"] or 0

        return {
            "high_risk_users": high_risk_users,
            "total_assessed_users": total_users,
            "avg_risk_score": round(avg_risk_score, 3),
            "risk_percentage": round((high_risk_users / total_users * 100), 2)
            if total_users > 0
            else 0,
        }

    def _get_trending_stats(self, start_date, end_date):
        """Get trending statistics"""
        # Get mood trend
        recent_snapshots = UserDataSnapshot.objects.filter(
            snapshot_date__gte=start_date, snapshot_date__lte=end_date
        )

        improving_users = (
            recent_snapshots.filter(mood_trend="improving")
            .values("user")
            .distinct()
            .count()
        )
        declining_users = (
            recent_snapshots.filter(mood_trend="declining")
            .values("user")
            .distinct()
            .count()
        )

        return {
            "improving_mood_users": improving_users,
            "declining_mood_users": declining_users,
            "trend_period": f"{(end_date - start_date).days} days",
        }


class DataExportView(viewsets.ViewSet):
    """Data export functionality"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def user_data(self, request):
        """Export user data in various formats"""
        user_id = request.query_params.get("user_id")
        export_format = request.query_params.get("format", "json")  # json, csv
        days = int(request.query_params.get("days", 30))

        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(id=user_id)

            # Get user snapshots
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)

            snapshots = UserDataSnapshot.objects.filter(
                user_id=user_id,
                snapshot_date__gte=start_date,
                snapshot_date__lte=end_date,
            ).order_by("-snapshot_date")

            if export_format == "json":
                serializer = UserDataSnapshotSerializer(snapshots, many=True)
                return Response(
                    {
                        "user_id": user_id,
                        "user_email": user.email,
                        "export_date": timezone.now(),
                        "period_days": days,
                        "data": serializer.data,
                    }
                )

            elif export_format == "csv":
                # For CSV export, we'd typically return a CSV file
                # For now, return a structured format that can be converted to CSV
                csv_data = []
                for snapshot in snapshots:
                    csv_data.append(
                        {
                            "date": snapshot.snapshot_date,
                            "mood_entries": snapshot.mood_entries_count,
                            "avg_mood_score": snapshot.avg_mood_score,
                            "journal_entries": snapshot.journal_entries_count,
                            "messages_sent": snapshot.messages_sent,
                            "risk_score": snapshot.risk_score,
                            "needs_attention": snapshot.needs_attention,
                        }
                    )

                return Response(
                    {"format": "csv_ready", "user_id": user_id, "data": csv_data}
                )

            else:
                return Response(
                    {"error": "Unsupported export format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error exporting data for user {user_id}: {str(e)}")
            return Response(
                {"error": f"Export failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def system_summary(self, request):
        """Export system-wide summary data"""
        try:
            export_format = request.query_params.get("format", "json")
            days = int(request.query_params.get("days", 30))

            # Generate comprehensive system summary
            summary_data = {
                "export_metadata": {
                    "generated_at": timezone.now(),
                    "period_days": days,
                    "format": export_format,
                },
                "user_statistics": {
                    "total_users": User.objects.count(),
                    "active_users": UserDataSnapshot.objects.filter(
                        snapshot_date__gte=timezone.now().date() - timedelta(days=days)
                    )
                    .values("user")
                    .distinct()
                    .count(),
                },
                "data_collection_summary": {
                    "total_snapshots": UserDataSnapshot.objects.count(),
                    "total_collection_runs": DataCollectionRun.objects.count(),
                    "successful_runs": DataCollectionRun.objects.filter(
                        status="completed"
                    ).count(),
                },
                "content_metrics": {
                    "total_mood_entries": UserDataSnapshot.objects.aggregate(
                        total=Sum("mood_entries_count")
                    )["total"]
                    or 0,
                    "total_journal_entries": UserDataSnapshot.objects.aggregate(
                        total=Sum("journal_entries_count")
                    )["total"]
                    or 0,
                    "total_messages": UserDataSnapshot.objects.aggregate(
                        total=Sum("messages_sent")
                    )["total"]
                    or 0,
                },
                "ml_models": {
                    "total_models": PredictiveModel.objects.count(),
                    "active_models": PredictiveModel.objects.filter(
                        is_active=True
                    ).count(),
                    "production_models": PredictiveModel.objects.filter(
                        is_production=True
                    ).count(),
                },
            }

            return Response(summary_data)

        except Exception as e:
            logger.error(f"Error generating system summary: {str(e)}")
            return Response(
                {"error": f"Summary export failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# New API ViewSets for Enhanced Services

class RealTimeAnalyticsViewSet(viewsets.ViewSet):
    """API endpoints for real-time analytics and streaming data"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def mood_monitoring(self, request):
        """Get real-time mood monitoring data"""
        try:
            # Get user_id from query params or use authenticated user
            user_id = request.query_params.get('user_id')
            if not user_id:
                # Use authenticated user's ID if no user_id provided
                user_id = str(request.user.id)
            
            data = realtime_service.get_mood_monitoring_data(user_id)
            return Response(data)
        except Exception as e:
            logger.error(f"Error in mood monitoring: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def crisis_detection(self, request):
        """Get crisis detection alerts"""
        try:
            alerts = realtime_service.get_crisis_alerts()
            return Response({'alerts': alerts})
        except Exception as e:
            logger.error(f"Error in crisis detection: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def system_metrics(self, request):
        """Get real-time system metrics"""
        try:
            metrics = realtime_service.get_system_metrics()
            return Response(metrics)
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def process_event(self, request):
        """Process a real-time event"""
        try:
            event_data = request.data
            result = realtime_service.process_event(event_data)
            return Response({'processed': True, 'result': result})
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditTrailViewSet(viewsets.ViewSet):
    """API endpoints for audit trail and compliance"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def audit_logs(self, request):
        """Get audit trail logs with filtering"""
        try:
            # Parse query parameters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            event_types = request.query_params.getlist('event_types')
            severity = request.query_params.get('severity')
            user_id = request.query_params.get('user_id')

            # Convert dates
            start_datetime = datetime.fromisoformat(start_date) if start_date else None
            end_datetime = datetime.fromisoformat(end_date) if end_date else None
            
            # Get user object if user_id provided
            user_obj = None
            if user_id:
                user_obj = User.objects.get(id=user_id)

            # Get audit trail
            audit_logs = audit_service.get_audit_trail(
                user=user_obj,
                start_date=start_datetime,
                end_date=end_datetime,
                event_types=event_types if event_types else None,
                severity=severity
            )

            # Serialize audit logs
            audit_data = []
            for log in audit_logs:
                audit_data.append({
                    'id': log.id,
                    'event_type': log.event_type,
                    'event_name': log.event_name,
                    'timestamp': log.timestamp.isoformat(),
                    'user': log.user.username if log.user else None,
                    'severity': log.severity,
                    'success': log.success,
                    'object_repr': log.object_repr,
                    'action_details': log.action_details
                })

            return Response({
                'audit_logs': audit_data,
                'total_count': len(audit_data)
            })

        except Exception as e:
            logger.error(f"Error retrieving audit logs: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def compliance_report(self, request):
        """Generate compliance report"""
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')

            # Use default date range (last 30 days) if not provided
            if not end_date:
                end_datetime = timezone.now()
                logger.info("Using current time as end_date for compliance report")
            else:
                try:
                    end_datetime = datetime.fromisoformat(end_date)
                except ValueError as e:
                    logger.error(f"Invalid end_date format: {end_date} - {str(e)}")
                    return Response(
                        {'error': f'Invalid end_date format: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
            if not start_date:
                start_datetime = end_datetime - timedelta(days=30)
                logger.info("Using default start_date (30 days before end_date) for compliance report")
            else:
                try:
                    start_datetime = datetime.fromisoformat(start_date)
                except ValueError as e:
                    logger.error(f"Invalid start_date format: {start_date} - {str(e)}")
                    return Response(
                        {'error': f'Invalid start_date format: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            report = audit_service.generate_compliance_report(
                start_datetime, end_datetime
            )
            
            # Add information about default date selection to the response
            if not start_date or not end_date:
                report['date_range_info'] = {
                    'used_default_dates': not (start_date and end_date),
                    'used_default_start_date': not start_date,
                    'used_default_end_date': not end_date,
                    'default_period_days': 30
                }

            return Response(report)

        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def verify_integrity(self, request):
        """Verify audit log integrity"""
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')

            start_datetime = datetime.fromisoformat(start_date) if start_date else None
            end_datetime = datetime.fromisoformat(end_date) if end_date else None

            integrity_report = audit_service.verify_audit_integrity(
                start_datetime, end_datetime
            )

            return Response(integrity_report)

        except Exception as e:
            logger.error(f"Error verifying integrity: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SecurityServiceViewSet(viewsets.ViewSet):
    """API endpoints for security and data protection"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def encrypt_data(self, request):
        """Encrypt sensitive data"""
        try:
            data = request.data.get('data')
            field_name = request.data.get('field_name', 'default')
            
            if not data:
                return Response(
                    {'error': 'data parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            encrypted_data = security_service.encrypt_field(data, field_name)
            return Response({'encrypted_data': encrypted_data})

        except Exception as e:
            logger.error(f"Error encrypting data: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def decrypt_data(self, request):
        """Decrypt sensitive data"""
        try:
            encrypted_data = request.data.get('encrypted_data')
            field_name = request.data.get('field_name', 'default')
            
            if not encrypted_data:
                return Response(
                    {'error': 'encrypted_data parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            decrypted_data = security_service.decrypt_field(encrypted_data, field_name)
            return Response({'decrypted_data': decrypted_data})

        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def mask_data(self, request):
        """Mask sensitive data for display"""
        try:
            data = request.data.get('data')
            mask_type = request.data.get('mask_type', 'partial')
            
            if not data:
                return Response(
                    {'error': 'data parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            masked_data = security_service.mask_sensitive_data(data, mask_type)
            return Response({'masked_data': masked_data})

        except Exception as e:
            logger.error(f"Error masking data: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def access_logs(self, request):
        """Get security access logs"""
        try:
            from .models import AccessLog
            
            # Filter parameters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            user_id = request.query_params.get('user_id')

            queryset = AccessLog.objects.all()

            if start_date:
                queryset = queryset.filter(timestamp__gte=datetime.fromisoformat(start_date))
            if end_date:
                queryset = queryset.filter(timestamp__lte=datetime.fromisoformat(end_date))
            if user_id:
                queryset = queryset.filter(user_id=user_id)

            access_logs = []
            for log in queryset.order_by('-timestamp')[:100]:  # Limit to recent 100
                access_logs.append({
                    'id': log.id,
                    'user': log.user.username if log.user else None,
                    'resource': log.resource_accessed,
                    'action': log.action_performed,
                    'timestamp': log.timestamp.isoformat(),
                    'ip_address': log.ip_address,
                    'success': log.access_granted
                })

            return Response({'access_logs': access_logs})

        except Exception as e:
            logger.error(f"Error retrieving access logs: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackupRecoveryViewSet(viewsets.ViewSet):
    """API endpoints for backup and recovery operations"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def create_backup(self, request):
        """Create a new backup"""
        try:
            backup_type = request.data.get('backup_type', 'full')
            description = request.data.get('description', 'Manual backup')
            include_media = request.data.get('include_media', True)

            job = backup_service.create_backup(
                backup_type=backup_type,
                description=description,
                include_media=include_media
            )

            return Response({
                'job_id': job.id,
                'status': job.status,
                'backup_type': job.backup_type,
                'started_at': job.started_at.isoformat()
            })

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def backup_status(self, request):
        """Get backup job status"""
        try:
            job_id = request.query_params.get('job_id')
            
            if not job_id:
                return Response(
                    {'error': 'job_id parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from .models import BackupJob
            job = BackupJob.objects.get(id=job_id)

            return Response({
                'job_id': job.id,
                'status': job.status,
                'backup_type': job.backup_type,
                'started_at': job.started_at.isoformat(),
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'file_path': job.backup_file_path,
                'file_size': job.backup_size_bytes,
                'error_message': job.error_message
            })

        except Exception as e:
            logger.error(f"Error getting backup status: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def backup_list(self, request):
        """List available backups"""
        try:
            from .models import BackupJob
            
            backups = BackupJob.objects.filter(
                status='completed'
            ).order_by('-completed_at')[:20]  # Latest 20 backups

            backup_list = []
            for backup in backups:
                backup_list.append({
                    'id': backup.id,
                    'backup_type': backup.backup_type,
                    'created_at': backup.started_at.isoformat(),
                    'file_size': backup.backup_size_bytes,
                    'description': backup.description,
                    'retention_until': backup.retention_until.isoformat() if backup.retention_until else None
                })

            return Response({'backups': backup_list})

        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def restore_backup(self, request):
        """Restore from backup"""
        try:
            backup_id = request.data.get('backup_id')
            restore_type = request.data.get('restore_type', 'full')
            
            if not backup_id:
                return Response(
                    {'error': 'backup_id parameter required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            job = backup_service.restore_backup(backup_id, restore_type)

            return Response({
                'restore_job_id': job.id,
                'status': job.status,
                'started_at': job.started_at.isoformat()
            })

        except Exception as e:
            logger.error(f"Error starting restore: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
