import json
import logging
import os
import argparse
from typing import Dict, List, Any
from datetime import datetime
from tqdm import tqdm

from django.conf import settings
from chatbot.services.chatbot_service import chatbot_service
from chatbot.services.rag.therapy_rag_service import therapy_rag_service
from chatbot.services.rag.evaluate_rag import RagEvaluator

logger = logging.getLogger(__name__)

# Define test cases with queries and expected response patterns
CHATBOT_TEST_CASES = [
    {
        "query": "I keep having negative thoughts that I can't get rid of. I think everyone hates me and I'll never be good enough.",
        "expected_approach": "cbt",
        "expected_keywords": [
            "cognitive distortion",
            "negative thought",
            "reframe",
            "evidence",
            "challenge",
        ],
    },
    {
        "query": "I have trouble controlling my emotions. One minute I'm fine, and the next I'm furious or devastated.",
        "expected_approach": "dbt",
        "expected_keywords": [
            "emotion regulation",
            "dialectical",
            "mindfulness",
            "validation",
        ],
    },
    {
        "query": "I struggle with black and white thinking. Everything is either perfect or terrible.",
        "expected_approach": "cbt",
        "expected_keywords": [
            "cognitive distortion",
            "all-or-nothing",
            "balanced perspective",
        ],
    },
    {
        "query": "I feel empty inside and often engage in self-destructive behaviors.",
        "expected_approach": "dbt",
        "expected_keywords": [
            "distress tolerance",
            "emotion regulation",
            "self-soothing",
        ],
    },
    {
        "query": "I worry constantly about everything that could go wrong.",
        "expected_approach": "cbt",
        "expected_keywords": ["worry", "anxiety", "catastrophizing", "evidence"],
    },
]


class ChatbotAccuracyTester:
    """Test the accuracy of chatbot responses against expected patterns"""

    def __init__(self, use_rag_test_cases=True, save_results=True):
        from ..services.rag.evaluate_rag import TEST_CASES as RAG_TEST_CASES

        # directory to save results
        self.save_dir = os.path.join(settings.BASE_DIR, "chatbot", "tests", "results")
        self.test_cases = CHATBOT_TEST_CASES.copy()
        if use_rag_test_cases:
            # Convert RAG test cases to chatbot test cases
            for case in RAG_TEST_CASES:
                self.test_cases.append(
                    {
                        "query": case["query"],
                        "expected_approach": case["expected_approach"],
                        "expected_keywords": self._get_keywords_for_approach(
                            case["expected_approach"]
                        ),
                    }
                )
        self.save_results = save_results
        self.results = []

    def _get_keywords_for_approach(self, approach: str) -> List[str]:
        """Get relevant keywords for a therapy approach"""
        if approach.lower() == "cbt":
            return [
                "cognitive",
                "thought",
                "evidence",
                "challenge",
                "restructuring",
                "distortion",
                "belief",
                "reframe",
                "thinking pattern",
                "negative thought",
                "cognitive distortion",
                "thought record",
                "core belief",
                "automatic thought",
                "evidence-based",
                "cognitive restructuring",
                "balanced thinking",
            ]
        elif approach.lower() == "dbt":
            return [
                "dialectical",
                "emotion regulation",
                "mindfulness",
                "distress tolerance",
                "interpersonal effectiveness",
                "validation",
                "acceptance",
                "dialectical behavior",
                "wise mind",
                "radical acceptance",
                "middle path",
                "distress tolerance",
                "emotional awareness",
                "self-soothe",
                "linehan",
                "mindful observation",
            ]
        else:
            return []

    def run_tests(self, mock_user=None) -> Dict[str, Any]:
        """Run all test cases and calculate metrics"""
        logger.info(f"Running {len(self.test_cases)} chatbot accuracy tests")

        total_cases = len(self.test_cases)
        approach_correct = 0
        keyword_scores = []

        for i, test_case in enumerate(tqdm(self.test_cases, desc="Testing chatbot")):
            query = test_case["query"]
            expected_approach = test_case["expected_approach"]
            expected_keywords = test_case["expected_keywords"]

            try:
                # First get therapy approach from RAG
                therapy_rec = therapy_rag_service.get_therapy_approach(query)
                actual_approach = therapy_rec.get("recommended_approach", "unknown")
                approach_match = actual_approach.lower() == expected_approach.lower()

                if approach_match:
                    approach_correct += 1

                # Get chatbot response
                response = chatbot_service.get_response(
                    user=mock_user,
                    message=query,
                    conversation_id="test",
                    conversation_history=[],
                )

                # Check for keyword matches
                keyword_score = self._calculate_keyword_score(
                    response["content"], expected_keywords
                )
                keyword_scores.append(keyword_score)

                # Store result
                result = {
                    "query": query,
                    "expected_approach": expected_approach,
                    "actual_approach": actual_approach,
                    "approach_match": approach_match,
                    "keyword_score": keyword_score,
                    "response_snippet": response["content"][:200] + "..."
                    if len(response["content"]) > 200
                    else response["content"],
                }
                self.results.append(result)

            except Exception as e:
                logger.error(f"Error testing case {i+1}: {str(e)}", exc_info=True)
                self.results.append(
                    {
                        "query": query,
                        "error": str(e),
                        "approach_match": False,
                        "keyword_score": 0.0,
                    }
                )

        # Calculate metrics
        approach_accuracy = approach_correct / total_cases if total_cases > 0 else 0
        avg_keyword_score = (
            sum(keyword_scores) / len(keyword_scores) if keyword_scores else 0
        )

        metrics = {
            "total_cases": total_cases,
            "approach_accuracy": approach_accuracy,
            "avg_keyword_score": avg_keyword_score,
            "comprehensive_score": (approach_accuracy + avg_keyword_score) / 2,
        }

        if self.save_results:
            self._save_results(metrics)

        return {
            "metrics": metrics,
            "results": self.results,
        }

    def _calculate_keyword_score(
        self, response_text: str, expected_keywords: List[str]
    ) -> float:
        """Calculate keyword match score (0-1) based on expected keywords in response"""
        if not response_text or not expected_keywords:
            return 0.0

        response_lower = response_text.lower()

        # Calculate matches with partial word matching to catch variations
        matches = 0
        matched_keywords = set()

        for keyword in expected_keywords:
            # Check for exact keyword match
            if keyword.lower() in response_lower:
                matches += 1
                matched_keywords.add(keyword)
                continue

            # Check for word variations (e.g., "cognitive" matches "cognition")
            keyword_parts = keyword.lower().split()
            if len(keyword_parts) == 1 and len(keyword_parts[0]) > 5:
                # For single words, check if at least the first 5 chars match
                keyword_root = keyword_parts[0][:5]
                words_in_response = response_lower.split()
                for word in words_in_response:
                    if (
                        word.startswith(keyword_root)
                        and keyword not in matched_keywords
                    ):
                        matches += 0.5  # Partial match counts as half
                        matched_keywords.add(keyword)
                        break

        return matches / len(expected_keywords) if expected_keywords else 0

    def _save_results(self, metrics: Dict[str, Any]) -> None:
        """Save test results to a file"""
        try:
            results_dir = self.save_dir
            os.makedirs(results_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(
                results_dir, f"chatbot_accuracy_results_{timestamp}.json"
            )

            with open(filename, "w") as f:
                json.dump(
                    {
                        "metrics": metrics,
                        "test_results": self.results,
                    },
                    f,
                    indent=2,
                )

            logger.info(f"Test results saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving test results: {str(e)}")


def run_tests(save: bool = False) -> dict:
    """
    Run chatbot accuracy tests using predefined test cases.

    Args:
        save (bool): Whether to save the results to a file.

    Returns:
        dict: Test results including metrics and detailed case results.
    """
    try:
        logger.info("Initializing chatbot accuracy tests...")
        evaluator = RagEvaluator(verbose=True)
        results = evaluator.run_evaluation()

        # Log summary metrics
        accuracy = results.get("accuracy", 0) * 100
        avg_confidence = results.get("average_confidence", 0) * 100
        logger.info(f"Accuracy: {accuracy:.2f}%")
        logger.info(f"Average Confidence: {avg_confidence:.2f}%")

        if "macro_f1" in results:
            logger.info(f"Macro F1 Score: {results['macro_f1']:.4f}")
            logger.info(f"CBT F1 Score: {results['class_metrics']['cbt']['f1']:.4f}")
            logger.info(f"DBT F1 Score: {results['class_metrics']['dbt']['f1']:.4f}")

        # Save results to a file if requested
        if save:
            results_file = "chatbot_accuracy_results.json"
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {results_file}")
            results["results_file"] = results_file

        return results

    except Exception as e:
        logger.error(f"Error running chatbot accuracy tests: {str(e)}", exc_info=True)
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Run chatbot accuracy tests")
    parser.add_argument("--no-rag", action="store_true", help="skip RAG test cases")
    parser.add_argument("--no-save", action="store_true", help="do not save results")
    parser.add_argument("--output-dir", help="directory to save results")
    args = parser.parse_args()

    tester = ChatbotAccuracyTester(
        use_rag_test_cases=not args.no_rag,
        save_results=not args.no_save,
    )
    if args.output_dir:
        tester.save_dir = args.output_dir

    results = tester.run_tests()
    print("Summary Metrics:")
    print(json.dumps(results["metrics"], indent=2))


if __name__ == "__main__":
    main()
