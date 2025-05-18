# chatbot/management/commands/cross_validate_chatbot.py
import json
import logging
from django.core.management.base import BaseCommand
from chatbot.services.rag.evaluate_rag import evaluate_and_save

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
        out = options.get("output")
        self.stdout.write(self.style.NOTICE("Starting cross-validation tests..."))

        try:
            # run full evaluation and get detailed metrics
            results = evaluate_and_save(output_file=out, verbose=True)
            # print JSON dump
            self.stdout.write(json.dumps(results, indent=2))
            # summary metrics
            acc = results.get("accuracy", results.get("summary", {}).get("accuracy"))
            macro_f1 = results.get("macro_f1")
            cbt_f1 = results.get("class_metrics", {}).get("cbt", {}).get("f1")
            dbt_f1 = results.get("class_metrics", {}).get("dbt", {}).get("f1")
            self.stdout.write(self.style.SUCCESS(f"Accuracy: {acc*100:.2f}%"))
            if macro_f1 is not None:
                self.stdout.write(self.style.SUCCESS(f"Macro F1: {macro_f1:.4f}"))
                self.stdout.write(
                    self.style.SUCCESS(f"CBT  F1: {cbt_f1:.4f}, DBT  F1: {dbt_f1:.4f}")
                )
            if out:
                self.stdout.write(self.style.SUCCESS(f"Results saved to {out}"))

            self.stdout.write(self.style.SUCCESS("Cross-validation completed."))
        except Exception as e:
            logger.error(f"Error during cross-validation: {str(e)}", exc_info=True)
            self.stderr.write(
                self.style.ERROR(f"Error during cross-validation: {str(e)}")
            )
