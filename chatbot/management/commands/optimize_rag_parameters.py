from django.core.management.base import BaseCommand
import numpy as np
import json
from chatbot.services.rag.evaluate_rag import TEST_CASES
from chatbot.services.rag.therapy_rag_service import therapy_rag_service

class Command(BaseCommand):
    help = "Find optimal parameter settings for the RAG system using grid search"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Output file for results",
            default="optimized_parameters.json"
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting parameter optimization..."))
        
        # Define parameter ranges to test
        similarity_thresholds = np.linspace(0.55, 0.85, 7)
        min_confidence_values = np.linspace(0.5, 0.8, 7)
        rule_confidence_boosts = np.linspace(0.05, 0.25, 5)
        
        original_similarity = therapy_rag_service.similarity_threshold
        original_confidence = therapy_rag_service.min_confidence
        original_boost = therapy_rag_service.rule_confidence_boost
        
        best_accuracy = 0.0
        best_params = {}
        all_results = []
        
        try:
            total_combinations = len(similarity_thresholds) * len(min_confidence_values) * len(rule_confidence_boosts)
            self.stdout.write(f"Testing {total_combinations} parameter combinations...")
            
            for sim_threshold in similarity_thresholds:
                for min_conf in min_confidence_values:
                    for rule_boost in rule_confidence_boosts:
                        # Set parameters
                        therapy_rag_service.similarity_threshold = sim_threshold
                        therapy_rag_service.min_confidence = min_conf
                        therapy_rag_service.rule_confidence_boost = rule_boost
                        
                        # Test with these parameters
                        correct = 0
                        for test_case in TEST_CASES:
                            query = test_case["query"]
                            expected = test_case["expected_approach"]
                            
                            recommendation = therapy_rag_service.get_therapy_approach(query)
                            predicted = recommendation.get("recommended_approach", "unknown")
                            
                            if predicted == expected:
                                correct += 1
                        
                        accuracy = correct / len(TEST_CASES)
                        result = {
                            "similarity_threshold": sim_threshold,
                            "min_confidence": min_conf,
                            "rule_confidence_boost": rule_boost,
                            "accuracy": accuracy
                        }
                        all_results.append(result)
                        
                        if accuracy > best_accuracy:
                            best_accuracy = accuracy
                            best_params = result.copy()
                            
                        self.stdout.write(f"Tested: sim={sim_threshold:.2f}, conf={min_conf:.2f}, boost={rule_boost:.2f} => accuracy={accuracy:.2f}")
            
            # Save results
            results = {
                "best_params": best_params,
                "all_results": all_results
            }
            
            with open(options["output"], "w") as f:
                json.dump(results, f, indent=2)
                
            self.stdout.write(self.style.SUCCESS(f"Best parameters found: {json.dumps(best_params, indent=2)}"))
            self.stdout.write(self.style.SUCCESS(f"Results saved to {options['output']}"))
            
        finally:
            # Restore original parameters
            therapy_rag_service.similarity_threshold = original_similarity
            therapy_rag_service.min_confidence = original_confidence
            therapy_rag_service.rule_confidence_boost = original_boost
