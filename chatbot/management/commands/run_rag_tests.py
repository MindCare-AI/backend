import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from chatbot.models import ChatbotConversation
from chatbot.services.rag.evaluate_rag import run_evaluation, TEST_CASES
from chatbot.services.chatbot_service import chatbot_service


class Command(BaseCommand):
    help = "Run RAG-only and end-to-end Gemini scenario tests and output JSON results"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Optional file path to write JSON results",
            default=None,
        )

    def handle(self, *args, **options):
        # RAG-only evaluation
        rag_results = run_evaluation()
        self.stdout.write(json.dumps(rag_results, indent=2))
        rag_acc = rag_results.get("summary", {}).get("accuracy", 0)
        self.stdout.write(self.style.SUCCESS(f"RAG-only Accuracy: {rag_acc*100:.2f}%"))

        # --- End-to-end scenario tests with Gemini chatbot ---
        self.stdout.write(self.style.NOTICE("Starting end-to-end scenario tests..."))
        User = get_user_model()
        user, _ = User.objects.get_or_create(username="e2e_test_user")

        # Replace get_or_create to avoid MultipleObjectsReturned
        conv_qs = ChatbotConversation.objects.filter(user=user, title="E2E Test")
        if conv_qs.exists():
            conv = conv_qs.first()
        else:
            conv = ChatbotConversation.objects.create(user=user, title="E2E Test")

        e2e_results = []
        for case in TEST_CASES:
            prompt = case["query"]
            expected = case["expected_approach"]
            # no conversation history for isolated prompts
            resp = chatbot_service.get_response(
                user=user,
                message=prompt,
                conversation_id=str(conv.id),
                conversation_history=[],
            )
            actual = (
                resp.get("metadata", {})
                .get("therapy_recommendation", {})
                .get("approach", "unknown")
            )
            confidence = (
                resp.get("metadata", {})
                .get("therapy_recommendation", {})
                .get("confidence", 0.0)
            )
            passed = actual == expected
            e2e_results.append(
                {
                    "query": prompt,
                    "expected": expected,
                    "actual": actual,
                    "confidence": confidence,
                    "pass": passed,
                }
            )

        total = len(e2e_results)
        passed_count = sum(1 for r in e2e_results if r["pass"])
        e2e_acc = passed_count / total if total else 0

        summary = {
            "total": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "accuracy": e2e_acc,
        }
        output = {"e2e_summary": summary, "e2e_results": e2e_results}

        self.stdout.write(json.dumps(output, indent=2))
        self.stdout.write(
            self.style.SUCCESS(f"End-to-end Accuracy: {e2e_acc*100:.2f}%")
        )

        out = options.get("output")
        if out:
            with open(out, "w") as f:
                f.write(json.dumps({"rag": rag_results, "e2e": output}, indent=2))
            self.stdout.write(self.style.SUCCESS(f"Results saved to {out}"))
