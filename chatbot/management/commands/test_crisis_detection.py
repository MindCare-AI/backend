from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from chatbot.services.chatbot_service import chatbot_service
from colorama import init, Fore, Style
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

# Initialize colorama
init()


class Command(BaseCommand):
    help = "Test the crisis detection and response system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--messages",
            type=str,
            nargs="+",
            help="Messages to test for crisis detection",
        )

        parser.add_argument(
            "--preset",
            action="store_true",
            help="Use preset test messages instead of custom ones",
        )

    def handle(self, *args, **options):
        test_messages = options.get("messages", [])
        use_preset = options.get("preset", False)

        if use_preset or not test_messages:
            test_messages = [
                "I'm feeling depressed today",  # Low risk
                "I don't know if life is worth living anymore",  # Medium risk
                "I want to kill myself",  # High risk
                "I have a plan to end my life tonight",  # Critical risk
                "My friend told me they're suicidal",  # Educational context
                "What should I do if someone says they want to die?",  # Educational context
                "I tried to kill myself yesterday",  # Past attempt
                "I'm going to hurt myself",  # Self-harm
                "I have the pills ready to take",  # Method mention
                "I can't take it anymore, I want to die",  # Indirect reference
            ]

        self.stdout.write(
            self.style.SUCCESS("\n===== Testing Crisis Detection System =====\n")
        )

        # Get any test user
        user = User.objects.first()
        if not user:
            self.stdout.write(
                self.style.ERROR("No user found for testing. Creating a test user...")
            )
            user = User.objects.create_user(
                username="test_user", email="test@example.com", password="testpassword"
            )

        for message in test_messages:
            # Test the enhanced crisis detection
            crisis_detection = chatbot_service._enhanced_crisis_detection(message)
            is_crisis = (
                crisis_detection["is_crisis"]
                and crisis_detection["confidence"]
                >= chatbot_service.min_crisis_confidence
            )

            # Generate appropriate color based on risk level
            if is_crisis:
                confidence = crisis_detection["confidence"]
                if confidence > 0.9:
                    color = Fore.RED
                    risk_level = "CRITICAL"
                elif confidence > 0.8:
                    color = Fore.MAGENTA
                    risk_level = "HIGH"
                else:
                    color = Fore.YELLOW
                    risk_level = "MEDIUM"
            else:
                color = Fore.GREEN
                risk_level = "LOW"

            # Display results
            self.stdout.write(f"\nMessage: {color}{message}{Style.RESET_ALL}")
            self.stdout.write(
                f"  Detected as crisis: {color}{is_crisis}{Style.RESET_ALL}"
            )
            self.stdout.write(
                f"  Confidence: {color}{crisis_detection['confidence']:.2f}{Style.RESET_ALL}"
            )
            self.stdout.write(
                f"  Category: {color}{crisis_detection['category']}{Style.RESET_ALL}"
            )
            self.stdout.write(f"  Risk Level: {color}{risk_level}{Style.RESET_ALL}")
            self.stdout.write(f"  Matched terms: {crisis_detection['matched_terms']}")

            # Generate and show response if it's a crisis
            if is_crisis:
                response = chatbot_service._generate_crisis_response(
                    user, message, crisis_detection
                )
                self.stdout.write("\n  Crisis Response Preview:")
                self.stdout.write(f"  {color}{'-' * 40}{Style.RESET_ALL}")
                self.stdout.write(f"  {response['content'][:200]}...")
                self.stdout.write(f"  {color}{'-' * 40}{Style.RESET_ALL}")
                self.stdout.write(
                    f"  Response Type: {response['metadata']['response_type']}"
                )

        self.stdout.write(
            self.style.SUCCESS("\n===== Crisis Detection Testing Complete =====")
        )
