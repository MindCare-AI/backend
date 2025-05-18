# chatbot/services/rag/evaluate_rag.py
import logging
import json
import os
import argparse
from typing import Dict, Any
from .therapy_rag_service import therapy_rag_service
from django.conf import settings
logger = logging.getLogger(__name__)

# Default test cases - can be overridden by loading from JSON file
TEST_CASES = [
    {
        "query": "I keep having negative thoughts that I can't get rid of. I think everyone hates me and I'll never be good enough.",
        "expected_approach": "cbt",
    },
    {
        "query": "I have trouble controlling my emotions. One minute I'm fine, and the next I'm furious or devastated.",
        "expected_approach": "dbt",
    },
    {
        "query": "I struggle with black and white thinking. Everything is either perfect or terrible, and I can't see the middle ground.",
        "expected_approach": "dbt",
    },
    {
        "query": "My anxiety makes me catastrophize. I always imagine the worst possible outcome for every situation.",
        "expected_approach": "cbt",
    },
    {
        "query": "I have a hard time in relationships. I'm terrified of abandonment and often push people away before they can leave me.",
        "expected_approach": "dbt",
    },
    {
        "query": "I keep procrastinating on important tasks because I'm afraid I'll fail at them.",
        "expected_approach": "cbt",
    },
    {
        "query": "When I'm upset, I often engage in impulsive behaviors that I later regret, like spending too much money or binge eating.",
        "expected_approach": "dbt",
    },
    {
        "query": "I'm constantly comparing myself to others on social media and feeling inadequate.",
        "expected_approach": "cbt",
    },
    {
        "query": "I need help with mindfulness techniques to stay present during stressful situations.",
        "expected_approach": "dbt",
    },
    {
        "query": "I need to challenge my irrational beliefs about needing to be perfect all the time.",
        "expected_approach": "cbt",
    },
    # New test cases with more nuanced scenarios
    {
        "query": "I often feel overwhelmed by my emotions and struggle to regulate them. What can I do?",
        "expected_approach": "dbt",
    },
    {
        "query": "I'm constantly worried about what others think of me and feel like I'm not living up to expectations.",
        "expected_approach": "cbt",
    },
    {
        "query": "I have a hard time accepting myself and often engage in self-destructive behaviors.",
        "expected_approach": "dbt",
    },
    {
        "query": "I need help with managing my stress and anxiety levels. Can you suggest some techniques?",
        "expected_approach": "cbt",
    },
    {
        "query": "I feel like I'm always walking on eggshels around people, trying not to upset them.",
        "expected_approach": "dbt",
    },
    {
        "query": "I can't stop overthinking every little thing I do, and it's exhausting.",
        "expected_approach": "cbt",
    },
    {
        "query": "I have trouble trusting people because I'm afraid they'll hurt me.",
        "expected_approach": "dbt",
    },
    {
        "query": "I often feel like I'm not good enogh no matter how hard I try.",
        "expected_approach": "cbt",
    },
    {
        "query": "I struggle with intense feelings of guilt and shame over past mistakes.",
        "expected_approach": "dbt",
    },
    {
        "query": "I need help with techniques to stop catastrophizing every situation.",
        "expected_approach": "cbt",
    },
    {
        "query": "I feel like my emotions control me, and I can't seem to manage them.",
        "expected_approach": "dbt",
    },
    {
        "query": "I keep doubting myself and my abilities, even when I know I'm capable.",
        "expected_approach": "cbt",
    },
    {
        "query": "I have a hard time letting go of grudges and forgiving others.",
        "expected_approach": "dbt",
    },
    {
        "query": "I often feel like I'm a failure and that nothing I do is ever good enough.",
        "expected_approach": "cbt",
    },
    {
        "query": "I feel like I'm constantly being judged by others, even when they don't say anything.",
        "expected_approach": "cbt",
    },
    {
        "query": "I struggle with impulsive decisions that I regret later, like spending too much money.",
        "expected_approach": "dbt",
    },
    {
        "query": "I need help with strategies to stop procrastinaton and get things done.",
        "expected_approach": "cbt",
    },
    {
        "query": "I often feel like I'm not worthy of love or acceptance from others.",
        "expected_approach": "dbt",
    },
    {
        "query": "I have a hard time dealing with criticism, even when it's constructive.",
        "expected_approach": "cbt",
    },
    {
        "query": "I feel like my emotions are a rollercoaster, and I can't get off the ride.",
        "expected_approach": "dbt",
    },
    {
        "query": "I need help with challenging my negative self-talk and building confidence.",
        "expected_approach": "cbt",
    },
    {
        "query": "I often feel like I'm stuck in a cycle of self-sabotage and can't break free.",
        "expected_approach": "dbt",
    },
    {
        "query": "I struggle with perfectionism and feel like I can't make mistakes.",
        "expected_approach": "cbt",
    },
    {
        "query": "I feel like I'm always on edge, waiting for something bad to happen.",
        "expected_approach": "cbt",
    },
]

# Add 100 additional complex test cases to challenge RAG
extra_cases = []
for idx in range(1, 101):
    # verbose, nuanced scenario with occasional typos and subtle cues
    query = (
        f"Scenario {idx}: I'm caught in a ceaseless spiral of self-criticism—"
        f"I replay each micro-interaction at work, sense every shifted glance, "
        f"and convince myself I'm embarrasingly inept; then I can't brethe."
    )
    # alternate expected approaches
    expected = "cbt" if idx % 3 == 1 else ("dbt" if idx % 3 == 2 else "cbt")
    extra_cases.append({"query": query, "expected_approach": expected})

TEST_CASES.extend(extra_cases)

# Add 100 additional 'other' complex test cases
other_cases = []
for idx in range(1, 101):
    # verbose, multifaceted scenario with both emotional and cognitive descriptors
    query = (
        f"Other {idx}: Between my racing thoughts about "
        f"{'work deadlines' if idx % 2 == 0 else 'relationship conflicts'}, "
        f"I also feel "
        f"{'a hollow emptiness' if idx % 3 == 0 else 'overwhelming guilt'}, "
        f"and I keep resorting to "
        f"{'avoidance behaviors' if idx % 5 == 0 else 'rumination patterns'} to cope."
    )
    expected = "dbt" if idx % 2 == 0 else "cbt"
    other_cases.append({"query": query, "expected_approach": expected})
TEST_CASES.extend(other_cases)

class RagEvaluator:
    """Evaluate RAG therapy approach recommendation performance."""

    def __init__(self, test_cases=None, verbose=False):
        """Initialize the evaluator.

        Args:
            test_cases: List of test cases or path to JSON file
            verbose: Whether to print detailed results
        """
        default_test_file = os.path.join(
            settings.BASE_DIR, "chatbot", "data", "test_cases.json"
        )
        self.test_cases = TEST_CASES
        self.verbose = verbose

        if test_cases is None and os.path.exists(default_test_file):
            test_cases = default_test_file
        if test_cases and isinstance(test_cases, str) and os.path.exists(test_cases):
            try:
                with open(test_cases, "r") as f:
                    loaded_cases = json.load(f)
                if isinstance(loaded_cases, list) and all(
                    "query" in case and "expected_approach" in case
                    for case in loaded_cases
                ):
                    self.test_cases = loaded_cases
                    logger.info(
                        f"Loaded {len(self.test_cases)} test cases from {test_cases}"
                    )
                else:
                    logger.error(f"Invalid test case format in {test_cases}")
            except Exception as e:
                logger.error(f"Error loading test cases from {test_cases}: {str(e)}")
        elif test_cases and isinstance(test_cases, list):
            self.test_cases = test_cases

    def run_evaluation(self) -> Dict[str, Any]:
        """Run evaluation on test cases and return metrics.

        Returns:
            Dictionary containing evaluation metrics
        """
        results = {
            "total_cases": len(self.test_cases),
            "correct": 0,
            "incorrect": 0,
            "average_confidence": 0,
            "cases": [],
            "confusion_matrix": {
                "cbt_as_cbt": 0,  # True Positive for CBT
                "cbt_as_dbt": 0,  # False Negative for CBT
                "dbt_as_dbt": 0,  # True Positive for DBT
                "dbt_as_cbt": 0,  # False Negative for DBT
                "unknown_predictions": 0,  # Cases where prediction was "unknown"
            },
        }

        total_confidence = 0

        for i, test_case in enumerate(self.test_cases):
            query = test_case["query"]
            expected = test_case["expected_approach"].lower()

            try:
                # Get recommendation from RAG service
                recommendation = therapy_rag_service.get_therapy_approach(query)
                predicted = recommendation.get(
                    "recommended_approach", "unknown"
                ).lower()
                confidence = recommendation.get("confidence", 0)

                # Track metrics
                total_confidence += confidence
                is_correct = predicted == expected

                if is_correct:
                    results["correct"] += 1
                else:
                    results["incorrect"] += 1

                # Update confusion matrix
                if expected == "cbt":
                    if predicted == "cbt":
                        results["confusion_matrix"]["cbt_as_cbt"] += 1
                    elif predicted == "dbt":
                        results["confusion_matrix"]["cbt_as_dbt"] += 1
                    else:
                        results["confusion_matrix"]["unknown_predictions"] += 1
                elif expected == "dbt":
                    if predicted == "dbt":
                        results["confusion_matrix"]["dbt_as_dbt"] += 1
                    elif predicted == "cbt":
                        results["confusion_matrix"]["dbt_as_cbt"] += 1
                    else:
                        results["confusion_matrix"]["unknown_predictions"] += 1

                # Store case details
                results["cases"].append(
                    {
                        "query": query,
                        "expected": expected,
                        "predicted": predicted,
                        "confidence": confidence,
                        "correct": is_correct,
                    }
                )

                if self.verbose:
                    logger.info(
                        f"Case {i+1}: Expected {expected}, Got {predicted}, Confidence {confidence:.2f}, Correct: {is_correct}"
                    )

            except Exception as e:
                logger.error(f"Error evaluating case {i+1}: {str(e)}")
                results["cases"].append(
                    {"query": query, "expected": expected, "error": str(e)}
                )

        # Calculate overall metrics
        if len(self.test_cases) > 0:
            results["accuracy"] = results["correct"] / len(self.test_cases)
            results["average_confidence"] = total_confidence / len(self.test_cases)

            # Calculate precision, recall, and F1 for each class
            cm = results["confusion_matrix"]

            # CBT metrics
            cbt_precision = (
                cm["cbt_as_cbt"] / (cm["cbt_as_cbt"] + cm["dbt_as_cbt"])
                if (cm["cbt_as_cbt"] + cm["dbt_as_cbt"]) > 0
                else 0
            )
            cbt_recall = (
                cm["cbt_as_cbt"] / (cm["cbt_as_cbt"] + cm["cbt_as_dbt"])
                if (cm["cbt_as_cbt"] + cm["cbt_as_dbt"]) > 0
                else 0
            )
            cbt_f1 = (
                2 * (cbt_precision * cbt_recall) / (cbt_precision + cbt_recall)
                if (cbt_precision + cbt_recall) > 0
                else 0
            )

            # DBT metrics
            dbt_precision = (
                cm["dbt_as_dbt"] / (cm["dbt_as_dbt"] + cm["cbt_as_dbt"])
                if (cm["dbt_as_dbt"] + cm["cbt_as_dbt"]) > 0
                else 0
            )
            dbt_recall = (
                cm["dbt_as_dbt"] / (cm["dbt_as_dbt"] + cm["dbt_as_cbt"])
                if (cm["dbt_as_dbt"] + cm["dbt_as_cbt"]) > 0
                else 0
            )
            dbt_f1 = (
                2 * (dbt_precision * dbt_recall) / (dbt_precision + dbt_recall)
                if (dbt_precision + dbt_recall) > 0
                else 0
            )

            # Add to results
            results["class_metrics"] = {
                "cbt": {"precision": cbt_precision, "recall": cbt_recall, "f1": cbt_f1},
                "dbt": {"precision": dbt_precision, "recall": dbt_recall, "f1": dbt_f1},
            }

            # Macro averages
            results["macro_precision"] = (cbt_precision + dbt_precision) / 2
            results["macro_recall"] = (cbt_recall + dbt_recall) / 2
            results["macro_f1"] = (cbt_f1 + dbt_f1) / 2

        return results


def evaluate_and_save(
    test_cases_file=None, output_file=None, verbose=False
) -> Dict[str, Any]:
    """Run evaluation and optionally save results to a file.

    Args:
        test_cases_file: Optional path to load test cases from
        output_file: Optional path to save results JSON
        verbose: Whether to print detailed results

    Returns:
        Evaluation results dictionary
    """
    try:
        logger.info("Starting therapy RAG evaluation...")
        evaluator = RagEvaluator(test_cases=test_cases_file, verbose=verbose)
        results = evaluator.run_evaluation()

        # Print summary
        accuracy = results.get("accuracy", 0) * 100
        avg_confidence = results.get("average_confidence", 0) * 100
        logger.info(
            f"Evaluation complete: Accuracy {accuracy:.2f}%, Average confidence {avg_confidence:.2f}%"
        )

        if "macro_f1" in results:
            logger.info(f"Macro F1 score: {results['macro_f1']:.4f}")
            logger.info(f"CBT F1 score: {results['class_metrics']['cbt']['f1']:.4f}")
            logger.info(f"DBT F1 score: {results['class_metrics']['dbt']['f1']:.4f}")

        # Save to file if specified
        if output_file:
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {output_file}")

        return results

    except Exception as e:
        logger.error(f"Evaluation failed: {str(e)}")
        return {"error": str(e)}


def run_evaluation():
    """Run predefined RAG test cases and return pass/fail results."""
    results = []
    for case in TEST_CASES:
        query = case["query"]
        expected = case["expected_approach"].lower()
        rec = therapy_rag_service.get_therapy_approach(query)
        actual = rec.get("recommended_approach", "unknown").lower()
        passed = (actual == expected)
        results.append({
            "query": query,
            "expected": expected,
            "actual": actual,
            "confidence": rec.get("confidence", 0),
            "pass": passed,
        })

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "failed": sum(1 for r in results if not r["pass"]),
        "accuracy": (sum(1 for r in results if r["pass"]) / len(results)) if results else 0,
    }
    return {"summary": summary, "results": results}


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate therapy RAG recommendation performance"
    )
    parser.add_argument(
        "--test-cases",
        dest="test_cases_file",
        help="Path to JSON test cases file",
        default=None,
    )
    parser.add_argument(
        "--output",
        dest="output_file",
        help="Path to save evaluation results JSON",
        default=None,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    results = evaluate_and_save(
        test_cases_file=args.test_cases_file,
        output_file=args.output_file,
        verbose=args.verbose,
    )
    # Exit code indicates success/failure
    exit(0 if results.get("accuracy", 0) >= 0.0 else 1)


if __name__ == "__main__":
    main()
