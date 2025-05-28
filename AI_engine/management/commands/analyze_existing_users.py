from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count
from AI_engine.services.ai_analysis import ai_service
from mood.models import MoodLog
from journal.models import JournalEntry
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
            # Find all users with mood logs and journal entries - use correct field names
            users_with_data = User.objects.annotate(
                mood_count=Count("mood_logs"),  # Changed from 'moodlog' to 'mood_logs'
                journal_count=Count(
                    "journal_entries"
                ),  # Changed from 'journalentry' to 'journal_entries'
            ).filter(mood_count__gt=0, journal_count__gt=0)

            self.stdout.write(
                f"Found {users_with_data.count()} users with mood logs and journal entries"
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
        """Analyze a specific user with enhanced logging and dry-run support"""
        try:
            # Check if user has recent data
            mood_count = MoodLog.objects.filter(user=user).count()
            journal_count = JournalEntry.objects.filter(user=user).count()

            self.stdout.write(
                f"Analyzing user {user.username} (ID: {user.id}) - "
                f"Moods: {mood_count}, Journals: {journal_count}"
            )

            # Run the analysis with dry run option
            if dry_run:
                self.stdout.write(
                    f"DRY RUN: Would analyze user {user.username} (ID: {user.id})"
                )
                # Preview analysis without saving
                preview = ai_service.analyze_user_data(
                    user, dry_run=True
                )
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
                        f"Recommendations: {result.get('recommendations_created', 0)}"
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
