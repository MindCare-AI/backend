#chatbot/services/rag/evaluate_rag.py
import logging
import json
from typing import Dict, Any
from .therapy_rag_service import therapy_rag_service

logger = logging.getLogger(__name__)

# Test cases with expected therapy approach
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
]


def run_evaluation() -> Dict[str, Any]:
    """Run evaluation on test cases and return metrics.

    Returns:
        Dictionary containing evaluation metrics
    """
    results = {
        "total_cases": len(TEST_CASES),
        "correct": 0,
        "incorrect": 0,
        "average_confidence": 0,
        "cases": [],
    }

    total_confidence = 0

    for i, test_case in enumerate(TEST_CASES):
        query = test_case["query"]
        expected = test_case["expected_approach"]

        try:
            # Get recommendation from RAG service
            recommendation = therapy_rag_service.get_therapy_approach(query)
            predicted = recommendation.get("recommended_approach", "unknown")
            confidence = recommendation.get("confidence", 0)

            # Track metrics
            total_confidence += confidence
            is_correct = predicted == expected

            if is_correct:
                results["correct"] += 1
            else:
                results["incorrect"] += 1

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

            logger.info(
                f"Case {i+1}: Expected {expected}, Got {predicted}, Confidence {confidence:.2f}, Correct: {is_correct}"
            )

        except Exception as e:
            logger.error(f"Error evaluating case {i+1}: {str(e)}")
            results["cases"].append(
                {"query": query, "expected": expected, "error": str(e)}
            )

    # Calculate overall metrics
    if len(TEST_CASES) > 0:
        results["accuracy"] = results["correct"] / len(TEST_CASES)
        results["average_confidence"] = total_confidence / len(TEST_CASES)

    return results


def evaluate_and_save(output_file: str = None) -> Dict[str, Any]:
    """Run evaluation and optionally save results to a file.

    Args:
        output_file: Optional path to save results JSON

    Returns:
        Evaluation results dictionary
    """
    try:
        logger.info("Starting therapy RAG evaluation...")
        results = run_evaluation()

        # Print summary
        accuracy = results.get("accuracy", 0) * 100
        avg_confidence = results.get("average_confidence", 0) * 100
        logger.info(
            f"Evaluation complete: Accuracy {accuracy:.2f}%, Average confidence {avg_confidence:.2f}%"
        )

        # Save to file if specified
        if output_file:
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {output_file}")

        return results

    except Exception as e:
        logger.error(f"Evaluation failed: {str(e)}")
        return {"error": str(e)}


if __name__ == "__main__":
    # This can be run as a standalone script
    logging.basicConfig(level=logging.INFO)
    evaluate_and_save("rag_evaluation_results.json")
