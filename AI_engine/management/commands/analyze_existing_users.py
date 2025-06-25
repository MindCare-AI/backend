from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from AI_engine.services.ai_analysis import ai_service
from AI_engine.services.data_interface import ai_data_interface
import logging
import os

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Analyze existing users who have mood logs and journal entries to generate therapy recommendations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Analyze specific user by ID",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days to analyze (default: 30)",
        )
        parser.add_argument(
            "--concurrent",
            action="store_true",
            help="Process users concurrently to speed up analysis",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview analysis without creating recommendations",
        )
        parser.add_argument(
            "--analysis-type",
            choices=["all", "mood", "journal", "medication", "communication"],
            default="all",
            help="Specify type of analysis to run",
        )

    def handle(self, *args, **kwargs):
        user_id = kwargs.get("user_id")
        days = kwargs.get("days", 30)

        if user_id:
            # Analyze specific user
            try:
                user = User.objects.get(id=user_id)
                self.analyze_user(user, days, kwargs.get("dry_run", False))
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User with ID {user_id} not found"))
                return
        else:
            # Find all users with sufficient data using AI data interface
            all_users = User.objects.all()
            users_with_data = []

            self.stdout.write("Checking users for sufficient data...")

            for user in all_users:
                # Use AI data interface to check data availability
                dataset = ai_data_interface.get_ai_ready_dataset(user.id, days)
                quality_metrics = dataset.get("quality_metrics", {})

                # Check if user has sufficient data for analysis
                if quality_metrics.get("overall_quality", 0.0) > 0.1:
                    users_with_data.append(user)

            self.stdout.write(
                f"Found {len(users_with_data)} users with sufficient data for analysis"
            )

            if kwargs.get("concurrent"):
                # Use ThreadPoolExecutor for parallel processing
                import concurrent.futures

                max_workers = min(10, os.cpu_count() or 4)  # Limit workers
                self.stdout.write(f"Processing with {max_workers} workers")

                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as executor:
                    futures = []
                    for user in users_with_data:
                        futures.append(
                            executor.submit(
                                self.analyze_user,
                                user,
                                days,
                                kwargs.get("dry_run", False),
                            )
                        )

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            self.stderr.write(
                                self.style.ERROR(f"Error in worker thread: {str(e)}")
                            )
            else:
                # Sequential processing (original behavior)
                for user in users_with_data:
                    self.analyze_user(user, days, kwargs.get("dry_run", False))

        self.stdout.write(self.style.SUCCESS("Analysis completed successfully"))

    def analyze_user(self, user, days, dry_run=False):
        """Analyze a specific user using AI data interface with enhanced logging and dry-run support"""
        try:
            # Use AI data interface to get user data summary
            dataset = ai_data_interface.get_ai_ready_dataset(user.id, days)
            quality_metrics = dataset.get("quality_metrics", {})
            data_sources = dataset.get("data_sources", [])

            # Extract data counts from dataset for logging
            mood_data = dataset.get("mood_data", [])
            journal_data = dataset.get("journal_data", [])
            mood_count = len(mood_data)
            journal_count = len(journal_data)

            self.stdout.write(
                f"Analyzing user {user.username} (ID: {user.id}) - "
                f"Moods: {mood_count}, Journals: {journal_count}, "
                f"Data Quality: {quality_metrics.get('overall_quality', 0.0):.2f}, "
                f"Sources: {', '.join(data_sources)}"
            )

            # Check if user has sufficient data
            if quality_metrics.get("overall_quality", 0.0) < 0.1:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ Insufficient data quality for {user.username}"
                    )
                )
                return

            # Run the analysis with dry run option
            if dry_run:
                self.stdout.write(
                    f"DRY RUN: Would analyze user {user.username} (ID: {user.id})"
                )
                # Preview analysis without saving
                preview = ai_service.analyze_user_data(user, dry_run=True)
                self.stdout.write(
                    f"Would create {preview.get('potential_recommendations', 0)} recommendations"
                )
                return

            # Run actual analysis
            result = ai_service.analyze_user_data(user)

            if result:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Analysis completed for {user.username} - "
                        f"Mood Score: {result.get('mood_score', 'N/A')}, "
                        f"Recommendations: {result.get('recommendations_created', 0)}, "
                        f"Data Integration Score: {quality_metrics.get('completeness', 0.0):.2f}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠ Analysis failed for {user.username}")
                )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error analyzing user {user.username}: {str(e)}")
            )
            logger.error(f"Error analyzing user {user.id}: {str(e)}", exc_info=True)
