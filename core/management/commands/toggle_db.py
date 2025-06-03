#core/management/commands/toggle_db.py
from django.core.management.base import BaseCommand
import os
from dotenv import load_dotenv, set_key
from pathlib import Path


class Command(BaseCommand):
    help = "Toggle between local and cloud database configurations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            type=str,
            help='Specify "local" or "cloud" to set database mode',
        )

    def handle(self, *args, **options):
        # Get the .env file path
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        env_path = os.path.join(base_dir, ".env")

        # Load current .env file
        load_dotenv(env_path)

        # Get current mode
        current_mode = os.getenv("USE_CLOUD", "True")
        is_cloud = current_mode.lower() in ("true", "yes", "1", "t")

        if options["mode"]:
            # Set the specified mode
            if options["mode"].lower() == "local":
                set_key(env_path, "USE_CLOUD", "False")
                self.stdout.write(self.style.SUCCESS("Database mode set to LOCAL"))
            elif options["mode"].lower() == "cloud":
                set_key(env_path, "USE_CLOUD", "True")
                self.stdout.write(self.style.SUCCESS("Database mode set to CLOUD"))
            else:
                self.stdout.write(
                    self.style.ERROR('Invalid mode. Use "local" or "cloud"')
                )
        else:
            # Toggle the current mode
            if is_cloud:
                set_key(env_path, "USE_CLOUD", "False")
                self.stdout.write(
                    self.style.SUCCESS("Database mode changed from CLOUD to LOCAL")
                )
            else:
                set_key(env_path, "USE_CLOUD", "True")
                self.stdout.write(
                    self.style.SUCCESS("Database mode changed from LOCAL to CLOUD")
                )

        self.stdout.write("Restart the server to apply changes.")
