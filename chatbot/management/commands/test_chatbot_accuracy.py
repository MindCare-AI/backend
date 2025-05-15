# chatbot/management/commands/test_chatbot_accuracy.py
from django.core.management.base import BaseCommand
from chatbot.tests.run_accuracy_tests import run_tests


class Command(BaseCommand):
    help = "Run chatbot accuracy tests"

    def add_arguments(self, parser):
        parser.add_argument(
            "--save",
            action="store_true",
            help="Save test results to file",
        )

    def handle(self, *args, **options):
        try:
            self.stdout.write(self.style.NOTICE("Running chatbot accuracy tests..."))
            results = run_tests(save=options.get("save", False))

            # Print main metrics
            accuracy = results["metrics"]["approach_accuracy"] * 100
            keyword_score = results["metrics"]["avg_keyword_score"] * 100
            comprehensive = results["metrics"]["comprehensive_score"] * 100

            self.stdout.write("\n=== Test Results ===")
            self.stdout.write(f"Approach Accuracy: {accuracy:.1f}%")
            self.stdout.write(f"Keyword Score: {keyword_score:.1f}%")
            self.stdout.write(f"Comprehensive Score: {comprehensive:.1f}%")

            if "results_file" in results:
                self.stdout.write(
                    f"\nDetailed results saved to: {results['results_file']}"
                )

            if results.get("success", False):
                self.stdout.write(self.style.SUCCESS("\nChatbot accuracy tests PASSED"))
            else:
                self.stderr.write(self.style.ERROR("\nChatbot accuracy tests FAILED"))
                self.stderr.write(
                    self.style.ERROR("Accuracy below required threshold (70%)")
                )
                exit(1)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error running tests: {str(e)}"))
            exit(1)
