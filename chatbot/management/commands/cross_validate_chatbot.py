# chatbot/management/commands/cross_validate_chatbot.py
import json
import logging
from django.core.management.base import BaseCommand
from chatbot.services.rag.evaluate_rag import run_evaluation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cross validate chatbot therapy recommendation using evaluation test cases"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Optional output file to save results in JSON format",
            default=None,
        )

    def handle(self, *args, **options):
        output_file = options.get("output")
        self.stdout.write(self.style.NOTICE("Starting cross-validation tests..."))

        try:
            results = run_evaluation()
            self.stdout.write(json.dumps(results, indent=2))

            if output_file:
                with open(output_file, "w") as f:
                    json.dump(results, f, indent=2)
                self.stdout.write(self.style.SUCCESS(f"Results saved to {output_file}"))

            self.stdout.write(self.style.SUCCESS("Cross-validation completed."))
        except Exception as e:
            logger.error(f"Error during cross-validation: {str(e)}", exc_info=True)
            self.stderr.write(
                self.style.ERROR(f"Error during cross-validation: {str(e)}")
            )
