import logging
from typing import Dict, Any, List
from chatbot.services.rag.therapy_rag_service import therapy_rag_service
from chatbot.services.rag.evaluate_rag import TEST_CASES
import json
import os
from django.conf import settings

logger = logging.getLogger(__name__)

# Parameter combinations to test
PARAMETER_SETS = [
    {
        "name": "default",
        "similarity_threshold": 0.65,
        "min_confidence": 0.6,
    },
    {
        "name": "high_precision",
        "similarity_threshold": 0.75,
        "min_confidence": 0.7,
    },
    {
        "name": "high_recall",
        "similarity_threshold": 0.55,
        "min_confidence": 0.5,
    }
]

def run_parametric_tests(test_cases=None, output_file=None):
    """Run tests with different parameter settings to find optimal configuration"""
    if test_cases is None:
        test_cases = TEST_CASES
    
    results = {
        "parameter_sets": [],
        "best_configuration": None,
        "best_accuracy": 0.0
    }
    
    # Save original parameters to restore later
    original_similarity = therapy_rag_service.similarity_threshold
    original_confidence = therapy_rag_service.min_confidence
    
    try:
        for params in PARAMETER_SETS:
            # Apply parameters
            therapy_rag_service.similarity_threshold = params["similarity_threshold"]
            therapy_rag_service.min_confidence = params["min_confidence"]
            
            # Run tests with these parameters
            param_results = evaluate_parameter_set(params, test_cases)
            results["parameter_sets"].append(param_results)
            
            # Check if this is the best so far
            if param_results["accuracy"] > results["best_accuracy"]:
                results["best_accuracy"] = param_results["accuracy"]
                results["best_configuration"] = params["name"]
                
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
                
        return results
    
    finally:
        # Restore original parameters
        therapy_rag_service.similarity_threshold = original_similarity
        therapy_rag_service.min_confidence = original_confidence

def evaluate_parameter_set(params: Dict[str, Any], test_cases: List[Dict[str, Any]]):
    """Evaluate a specific parameter set against test cases"""
    correct = 0
    cases = []
    
    for test_case in test_cases:
        query = test_case["query"]
        expected = test_case["expected_approach"]
        
        try:
            # Get recommendation with current parameters
            recommendation = therapy_rag_service.get_therapy_approach(query)
            predicted = recommendation.get("recommended_approach", "unknown")
            confidence = recommendation.get("confidence", 0)
            
            is_correct = predicted == expected
            if is_correct:
                correct += 1
                
            cases.append({
                "query": query,
                "expected": expected,
                "predicted": predicted,
                "confidence": confidence,
                "correct": is_correct
            })
            
        except Exception as e:
            logger.error(f"Error evaluating case '{query}': {str(e)}")
            cases.append({
                "query": query,
                "expected": expected,
                "error": str(e)
            })
    
    # Calculate metrics
    accuracy = correct / len(test_cases) if test_cases else 0
    
    return {
        "name": params["name"],
        "parameters": params,
        "accuracy": accuracy,
        "correct": correct,
        "total": len(test_cases),
        "cases": cases
    }

if __name__ == "__main__":
    results = run_parametric_tests(output_file="parametric_results.json")
    for param_set in results["parameter_sets"]:
        print(f"{param_set['name']}: {param_set['accuracy']:.2f} accuracy")
    print(f"Best configuration: {results['best_configuration']} ({results['best_accuracy']:.2f})")
