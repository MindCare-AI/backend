# datawarehouse/services/etl_service.py
"""
Enterprise ETL Service for MindCare Data Warehouse
Handles Extract, Transform, Load operations with modern Python tools
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import pandas as pd
import numpy as np
import logging

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

# Import our models and services
from ..models import DataCollectionRun, UserDataSnapshot

User = get_user_model()


@dataclass
class ETLJob:
    """Represents an ETL job with metadata"""

    job_id: str
    job_type: str
    status: str = "pending"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    records_processed: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ETLService:
    """
    Enterprise ETL Service for data warehouse operations

    Features:
    - Batch processing with pandas
    - Data quality validation
    - Error handling and recovery
    - Performance monitoring
    - Incremental data loading
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.cache_timeout = 3600  # 1 hour

    def run_full_etl(self, user_ids: Optional[List[int]] = None) -> ETLJob:
        """
        Run full ETL process for specified users or all users

        Args:
            user_ids: List of user IDs to process, or None for all users

        Returns:
            ETLJob: Job metadata and results
        """
        job = ETLJob(
            job_id=f"full_etl_{int(time.time())}",
            job_type="full_sync",
            start_time=timezone.now(),
        )

        try:
            logger.info("Starting full ETL process", job_id=job.job_id)

            # Create collection run record
            collection_run = DataCollectionRun.objects.create(
                run_type="full_sync", metadata={"job_id": job.job_id}
            )

            job.status = "running"

            # Get users to process
            if user_ids:
                users = User.objects.filter(id__in=user_ids)
            else:
                users = User.objects.filter(is_active=True)

            logger.info(f"Processing {users.count()} users")

            # Process users in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_user = {
                    executor.submit(self._process_user_data, user): user
                    for user in users
                }

                for future in as_completed(future_to_user):
                    user = future_to_user[future]
                    try:
                        result = future.result()
                        job.records_processed += result.get("records_processed", 0)
                    except Exception as e:
                        error_msg = f"Error processing user {user.id}: {str(e)}"
                        job.errors.append(error_msg)

            job.status = "completed" if not job.errors else "partial"
            job.end_time = timezone.now()

            # Update collection run
            collection_run.status = (
                "completed" if job.status == "completed" else "partial"
            )
            collection_run.completed_at = job.end_time
            collection_run.records_processed = job.records_processed
            collection_run.errors_count = len(job.errors)
            collection_run.metadata.update(
                {
                    "job_result": job.status,
                    "processing_time_seconds": (
                        job.end_time - job.start_time
                    ).total_seconds(),
                    "errors": job.errors[:10],  # Store first 10 errors
                }
            )
            collection_run.save()

            logger.info(
                "ETL process completed",
                job_id=job.job_id,
                status=job.status,
                records_processed=job.records_processed,
                errors_count=len(job.errors),
            )

        except Exception as e:
            job.status = "failed"
            job.end_time = timezone.now()
            job.errors.append(f"ETL process failed: {str(e)}")
            logger.error("ETL process failed", job_id=job.job_id, exc_info=True)
            raise

        return job

    def run_incremental_etl(self, since: Optional[datetime] = None) -> ETLJob:
        """
        Run incremental ETL process for recent changes

        Args:
            since: Process changes since this datetime, or last 24 hours if None

        Returns:
            ETLJob: Job metadata and results
        """
        if since is None:
            since = timezone.now() - timedelta(hours=24)

        job = ETLJob(
            job_id=f"incremental_etl_{int(time.time())}",
            job_type="incremental",
            start_time=timezone.now(),
            metadata={"since": since.isoformat()},
        )

        try:
            logger.info(
                "Starting incremental ETL process", job_id=job.job_id, since=since
            )

            # Create collection run record
            collection_run = DataCollectionRun.objects.create(
                run_type="incremental",
                metadata={"job_id": job.job_id, "since": since.isoformat()},
            )

            job.status = "running"

            # Find users with recent activity
            active_users = self._find_recently_active_users(since)
            logger.info(f"Processing {len(active_users)} recently active users")

            # Process users in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_user = {
                    executor.submit(self._process_user_data, user, since): user
                    for user in active_users
                }

                for future in as_completed(future_to_user):
                    user = future_to_user[future]
                    try:
                        result = future.result()
                        job.records_processed += result.get("records_processed", 0)
                        logger.debug(f"Processed user {user.id}", **result)
                    except Exception as e:
                        error_msg = f"Error processing user {user.id}: {str(e)}"
                        job.errors.append(error_msg)
                        logger.error(error_msg, user_id=user.id, exc_info=True)

            job.status = "completed" if not job.errors else "partial"
            job.end_time = timezone.now()

            # Update collection run
            collection_run.status = (
                "completed" if job.status == "completed" else "partial"
            )
            collection_run.completed_at = job.end_time
            collection_run.records_processed = job.records_processed
            collection_run.errors_count = len(job.errors)
            collection_run.save()

            logger.info(
                "Incremental ETL process completed",
                job_id=job.job_id,
                status=job.status,
                records_processed=job.records_processed,
                errors_count=len(job.errors),
            )

        except Exception as e:
            job.status = "failed"
            job.end_time = timezone.now()
            job.errors.append(f"Incremental ETL process failed: {str(e)}")
            logger.error(
                "Incremental ETL process failed", job_id=job.job_id, exc_info=True
            )
            raise

        return job

    def _process_user_data(
        self, user: "AbstractUser", since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Process data for a single user

        Args:
            user: User to process
            since: Process data since this datetime, or all data if None

        Returns:
            Dict with processing results
        """
        start_time = time.time()
        records_processed = 0

        try:
            # Collect user data using our data collection service
            try:
                from .data_collection import data_collector
                user_data = data_collector.collect_user_data(user.id)
            except ImportError:
                user_data = None

            if not user_data:
                return {
                    "user_id": user.id,
                    "records_processed": 0,
                    "processing_time": time.time() - start_time,
                    "status": "no_data",
                }

            # Transform data using pandas for efficient processing
            df_data = pd.DataFrame([user_data.__dict__ if hasattr(user_data, '__dict__') else {}])

            # Apply data transformations
            transformed_data = self._transform_user_data(df_data, user)

            # Load data into warehouse models
            snapshot = self._create_user_snapshot(user, transformed_data)
            if snapshot:
                records_processed += 1

            # Cache processed data for quick access
            cache_key = f"user_data_{user.id}_{int(time.time() // 3600)}"
            cache.set(cache_key, transformed_data.to_dict(), timeout=self.cache_timeout)

            return {
                "user_id": user.id,
                "records_processed": records_processed,
                "processing_time": time.time() - start_time,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Error processing user {user.id}", exc_info=True)
            return {
                "user_id": user.id,
                "records_processed": records_processed,
                "processing_time": time.time() - start_time,
                "status": "error",
                "error": str(e),
            }

    def _transform_user_data(self, df: pd.DataFrame, user: "AbstractUser") -> pd.DataFrame:
        """Transform raw user data using pandas"""
        try:
            # Create a copy to avoid modifying original data
            transformed = df.copy()

            # Add user metadata
            transformed["user_id"] = user.id
            transformed["processed_at"] = timezone.now()

            # Process mood data if available
            if "mood_data" in transformed.columns and not transformed["mood_data"].isna().all():
                mood_data = transformed["mood_data"].iloc[0]
                if isinstance(mood_data, dict) and mood_data.get("entries"):
                    mood_scores = [entry.get("mood_score", 0) for entry in mood_data["entries"]]
                    if mood_scores:
                        transformed["avg_mood_score"] = np.mean(mood_scores)
                        transformed["mood_volatility"] = np.std(mood_scores)

            return transformed

        except Exception:
            logger.error("Error transforming user data", user_id=user.id, exc_info=True)
            return df

    def _create_user_snapshot(self, user: "AbstractUser", transformed_data: pd.DataFrame) -> Optional[UserDataSnapshot]:
        """Create or update user data snapshot"""
        try:
            snapshot_date = timezone.now().date()

            # Get or create snapshot for today
            snapshot, created = UserDataSnapshot.objects.get_or_create(
                user=user, snapshot_date=snapshot_date, defaults={}
            )

            # Update snapshot with transformed data
            if not transformed_data.empty:
                row = transformed_data.iloc[0]
                if "avg_mood_score" in row and pd.notna(row["avg_mood_score"]):
                    snapshot.avg_mood_score = float(row["avg_mood_score"])

            snapshot.last_updated = timezone.now()
            snapshot.save()

            return snapshot

        except Exception:
            logger.error(f"Error creating snapshot for user {user.id}", exc_info=True)
            return None

    def _find_recently_active_users(self, since: datetime) -> List["AbstractUser"]:
        """
        Find users with recent activity

        Args:
            since: Find users active since this datetime

        Returns:
            List of active users
        """
        try:
            # This is a simplified version - in reality, you'd check multiple tables
            # for user activity (mood entries, journal entries, messages, etc.)

            # For now, return all active users for incremental processing
            # In a real implementation, you'd check various activity tables
            return list(User.objects.filter(is_active=True))

        except Exception:
            logger.error("Error finding recently active users", exc_info=True)
            return []

    def get_etl_status(self) -> Dict[str, Any]:
        """
        Get current ETL status and statistics

        Returns:
            Dict with ETL status information
        """
        try:
            # Get recent collection runs
            recent_runs = DataCollectionRun.objects.filter(
                started_at__gte=timezone.now() - timedelta(days=7)
            ).order_by("-started_at")[:10]

            # Calculate statistics
            total_runs = recent_runs.count()
            successful_runs = recent_runs.filter(status="completed").count()
            failed_runs = recent_runs.filter(status="failed").count()

            latest_run = recent_runs.first() if recent_runs else None

            return {
                "status": "operational",
                "recent_stats": {
                    "total_runs_7_days": total_runs,
                    "successful_runs": successful_runs,
                    "failed_runs": failed_runs,
                    "success_rate": (successful_runs / total_runs * 100)
                    if total_runs > 0
                    else 0,
                },
                "latest_run": {
                    "run_type": latest_run.run_type if latest_run else None,
                    "status": latest_run.status if latest_run else None,
                    "started_at": latest_run.started_at if latest_run else None,
                    "records_processed": latest_run.records_processed
                    if latest_run
                    else 0,
                }
                if latest_run
                else None,
                "timestamp": timezone.now(),
            }

        except Exception as e:
            logger.error("Error getting ETL status", exc_info=True)
            return {"status": "error", "error": str(e), "timestamp": timezone.now()}


# Global ETL service instance
etl_service = ETLService()
