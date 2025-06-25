# datawarehouse/management/commands/populate_datawarehouse.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging
import numpy as np
from scipy import stats
from collections import defaultdict

from datawarehouse.models import MoodTrendAnalysis, DataCollectionRun
from mood.models import MoodLog

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Populate datawarehouse with analysis data from source models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            nargs="+",
            type=int,
            help="Specific user IDs to process (default: all users)",
        )
        parser.add_argument(
            "--analysis-types",
            nargs="+",
            choices=["mood", "journal", "communication", "features", "snapshots"],
            default=["mood", "journal", "communication", "features", "snapshots"],
            help="Types of analysis to run",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Number of days back to analyze (default: 90)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force regeneration of existing analyses",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting datawarehouse population..."))

        # Create data collection run record
        run = DataCollectionRun.objects.create(
            run_type="incremental",
            status="running",
            metadata={"command": "populate_datawarehouse", "options": options},
        )

        try:
            # Get users to process
            if options["users"]:
                users = User.objects.filter(id__in=options["users"])
            else:
                users = User.objects.filter(is_active=True)

            self.stdout.write(f"Processing {users.count()} users...")

            total_processed = 0
            errors_count = 0

            for user in users:
                try:
                    self.stdout.write(f"Processing user {user.id}: {user.username}")

                    if "mood" in options["analysis_types"]:
                        mood_count = self.populate_mood_analysis(
                            user, options["days"], options["force"]
                        )
                        total_processed += mood_count

                    if "journal" in options["analysis_types"]:
                        journal_count = self.populate_journal_analysis(
                            user, options["days"], options["force"]
                        )
                        total_processed += journal_count

                    if "communication" in options["analysis_types"]:
                        comm_count = self.populate_communication_analysis(
                            user, options["days"], options["force"]
                        )
                        total_processed += comm_count

                    if "features" in options["analysis_types"]:
                        feature_count = self.populate_feature_analysis(
                            user, options["days"], options["force"]
                        )
                        total_processed += feature_count

                    if "snapshots" in options["analysis_types"]:
                        snapshot_count = self.populate_user_snapshots(
                            user, options["days"], options["force"]
                        )
                        total_processed += snapshot_count

                except Exception as e:
                    errors_count += 1
                    logger.error(f"Error processing user {user.id}: {str(e)}")
                    self.stdout.write(
                        self.style.ERROR(f"Error processing user {user.id}: {str(e)}")
                    )

            # Update run status
            run.status = "completed"
            run.completed_at = timezone.now()
            run.records_processed = total_processed
            run.errors_count = errors_count
            run.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Datawarehouse population completed. "
                    f"Processed {total_processed} records with {errors_count} errors."
                )
            )

        except Exception as e:
            run.status = "failed"
            run.completed_at = timezone.now()
            run.errors_count += 1
            run.metadata["error"] = str(e)
            run.save()
            raise

    def populate_mood_analysis(self, user, days_back, force):
        """Generate mood trend analyses for a user"""
        count = 0

        # Get mood logs for the user
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)

        # Use logged_at instead of created_at to filter mood logs
        mood_logs = MoodLog.objects.filter(
            user=user, logged_at__date__gte=start_date, logged_at__date__lte=end_date
        ).order_by("logged_at")

        if not mood_logs.exists():
            self.stdout.write(
                f"  No mood logs found for user {user.id} in the last {days_back} days"
            )
            return count

        self.stdout.write(f"  Found {mood_logs.count()} mood logs for user {user.id}")

        # Generate weekly and monthly analyses
        analysis_periods = [
            ("weekly", 14),  # 2 weeks
            ("monthly", 30),
        ]

        for analysis_type, period_days in analysis_periods:
            period_start = end_date - timedelta(days=period_days)

            # Check if analysis already exists
            existing = MoodTrendAnalysis.objects.filter(
                user=user,
                analysis_type=analysis_type,
                period_start=period_start,
                period_end=end_date,
            ).first()

            if existing and not force:
                self.stdout.write(
                    f"  Skipping existing {analysis_type} analysis for user {user.id}"
                )
                continue

            # Use logged_at instead of created_at
            period_logs = mood_logs.filter(logged_at__date__gte=period_start)

            if period_logs.count() < 2:
                self.stdout.write(
                    f"  Not enough data for {analysis_type} analysis (need at least 2 entries, found {period_logs.count()})"
                )
                continue

            # Calculate trend analysis
            analysis_data = self.calculate_mood_trends(period_logs)

            # Create or update analysis
            analysis, created = MoodTrendAnalysis.objects.update_or_create(
                user=user,
                analysis_type=analysis_type,
                period_start=period_start,
                period_end=end_date,
                defaults=analysis_data,
            )

            count += 1
            action = "Created" if created else "Updated"
            self.stdout.write(
                f"  {action} {analysis_type} mood analysis for user {user.id}"
            )

        return count

    def calculate_mood_trends(self, mood_logs):
        """Calculate mood trend metrics from mood logs"""
        # Convert to lists for analysis
        dates = []
        moods = []
        activities = defaultdict(list)

        for log in mood_logs:
            dates.append(log.logged_at.date())
            moods.append(float(log.mood_rating))
            if log.activities:
                activities[log.activities].append(float(log.mood_rating))

        # Convert dates to numeric for regression
        base_date = min(dates)
        x_values = [(d - base_date).days for d in dates]
        y_values = moods

        # Calculate trend direction using linear regression
        if len(x_values) > 1:
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                x_values, y_values
            )
            trend_strength = abs(r_value)

            # Determine trend direction
            if slope > 0.5:
                trend_direction = "strongly_improving"
            elif slope > 0.1:
                trend_direction = "improving"
            elif slope < -0.5:
                trend_direction = "strongly_declining"
            elif slope < -0.1:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            slope = 0
            trend_direction = "stable"
            trend_strength = 0

        # Calculate statistics
        mood_array = np.array(moods)
        avg_mood = float(np.mean(mood_array))
        median_mood = float(np.median(mood_array))
        min_mood = float(np.min(mood_array))
        max_mood = float(np.max(mood_array))
        mood_range = max_mood - min_mood
        volatility_score = float(np.std(mood_array))

        # Calculate consistency (inverse of volatility, normalized)
        consistency_score = max(0, 1 - (volatility_score / 5))  # Assuming 1-10 scale

        # Calculate activity correlations
        correlation_data = {}
        for activity, activity_moods in activities.items():
            if len(activity_moods) > 1:
                activity_avg = np.mean(activity_moods)
                correlation_data[activity] = {
                    "average_mood": float(activity_avg),
                    "sessions": len(activity_moods),
                    "compared_to_overall": float(activity_avg - avg_mood),
                }

        # Daily averages pattern
        daily_averages = defaultdict(list)
        for date, mood in zip(dates, moods):
            daily_averages[date.strftime("%Y-%m-%d")].append(mood)

        pattern_data = {
            "daily_averages": {
                date: float(np.mean(moods)) for date, moods in daily_averages.items()
            },
            "trend_slope": float(slope) if slope else 0,
            "data_points": len(moods),
        }

        # Simple prediction (next period average based on trend)
        next_period_prediction = avg_mood + (slope * 7)  # Project 7 days ahead
        next_period_prediction = max(
            1, min(10, next_period_prediction)
        )  # Clamp to 1-10 range
        prediction_confidence = min(0.9, trend_strength)  # Cap at 90%

        return {
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "volatility_score": volatility_score,
            "consistency_score": consistency_score,
            "avg_mood": avg_mood,
            "median_mood": median_mood,
            "min_mood": min_mood,
            "max_mood": max_mood,
            "mood_range": mood_range,
            "pattern_data": pattern_data,
            "correlation_data": correlation_data,
            "anomalies": [],  # TODO: Implement anomaly detection
            "next_period_prediction": next_period_prediction,
            "prediction_confidence": prediction_confidence,
        }

    def populate_journal_analysis(self, user, days_back, force):
        """Generate journal insight cache for a user"""
        # Placeholder for journal analysis
        # This would be implemented similar to mood analysis
        self.stdout.write(f"  Journal analysis not yet implemented for user {user.id}")
        return 0

    def populate_communication_analysis(self, user, days_back, force):
        """Generate communication metrics for a user"""
        # Placeholder for communication analysis
        self.stdout.write(
            f"  Communication analysis not yet implemented for user {user.id}"
        )
        return 0

    def populate_feature_analysis(self, user, days_back, force):
        """Generate feature usage metrics for a user"""
        # Placeholder for feature analysis
        self.stdout.write(f"  Feature analysis not yet implemented for user {user.id}")
        return 0

    def populate_user_snapshots(self, user, days_back, force):
        """Generate daily user data snapshots"""
        # Placeholder for snapshot generation
        self.stdout.write(f"  User snapshots not yet implemented for user {user.id}")
        return 0
