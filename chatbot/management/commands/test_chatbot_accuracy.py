import subprocess
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Run chatbot accuracy tests"

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            action='store_true',
            help='Save test results to file',
        )

    def handle(self, *args, **options):
        # invoke the test runner script
        proc = subprocess.run(
            ["python", "-m", "chatbot.tests.run_accuracy_tests"],
            capture_output=True,
            text=True,
        )
        self.stdout.write(proc.stdout)
        if proc.returncode != 0:
            self.stderr.write(self.style.ERROR("Some accuracy tests failed"))
            exit(proc.returncode)
        self.stdout.write(self.style.SUCCESS("All accuracy tests passed"))
