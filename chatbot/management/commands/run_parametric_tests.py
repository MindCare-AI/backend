from django.core.management.base import BaseCommand
from chatbot.tests.parametric_tests import run_parametric_tests


class Command(BaseCommand):
    help = "Run parametric tests to find optimal RAG configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Output file for results",
            default="parametric_results.json"
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Running parametric tests..."))
        results = run_parametric_tests(output_file=options["output"])
        
        self.stdout.write("\n=== Results by Configuration ===")
        for param_set in results["parameter_sets"]:
            accuracy = param_set["accuracy"] * 100
            self.stdout.write(f"{param_set['name']}: {accuracy:.1f}% accuracy")
        
        best = results["best_configuration"]
        best_acc = results["best_accuracy"] * 100
        self.stdout.write(self.style.SUCCESS(f"\nBest configuration: {best} ({best_acc:.1f}%)"))
        self.stdout.write(f"Detailed results saved to: {options['output']}")
