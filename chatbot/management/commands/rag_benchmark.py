import time
import json
import statistics
from django.core.management.base import BaseCommand
from chatbot.services.rag.therapy_rag_service import therapy_rag_service
from chatbot.services.rag.evaluate_rag import TEST_CASES
from chatbot.tests.parametric_tests import run_parametric_tests
import psutil
import os

class Command(BaseCommand):
    help = "Run comprehensive RAG system benchmarks"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', 
            type=str,
            help='Output file for benchmark results',
            default='benchmark_results.json'
        )
        parser.add_argument(
            '--iterations', 
            type=int,
            help='Number of iterations for performance testing',
            default=3
        )
        parser.add_argument(
            '--parametric', 
            action='store_true',
            help='Run parametric testing'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        iterations = options['iterations']
        run_parametric = options['parametric']
        
        try:
            self.stdout.write(self.style.NOTICE("Starting RAG system benchmarks..."))
            
            results = {
                "accuracy": {},
                "performance": {},
                "system_info": self._get_system_info(),
            }
            
            # Run accuracy tests
            self.stdout.write("Running accuracy tests...")
            accuracy_results = self._run_accuracy_tests()
            results["accuracy"] = accuracy_results
            
            # Run performance tests
            self.stdout.write("Running performance tests...")
            performance_results = self._run_performance_tests(iterations)
            results["performance"] = performance_results
            
            # Run parametric tests if requested
            if run_parametric:
                self.stdout.write("Running parametric tests...")
                parametric_results = run_parametric_tests(TEST_CASES)
                results["parametric"] = parametric_results
            
            # Save results
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
                
            self.stdout.write(self.style.SUCCESS(f"Benchmarks completed and saved to {output_file}"))
            
            # Print summary
            self._print_summary(results)
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error running benchmarks: {str(e)}"))
    
    def _run_accuracy_tests(self):
        """Run accuracy tests using test cases"""
        from chatbot.services.rag.evaluate_rag import run_evaluation
        return run_evaluation()
    
    def _run_performance_tests(self, iterations):
        """Measure performance metrics including response time and memory usage"""
        results = {
            "response_times": [],
            "avg_response_time": 0,
            "memory_usage": [],
            "avg_memory_usage": 0,
        }
        
        # Sample test queries from test cases
        test_queries = [case["query"] for case in TEST_CASES[:5]]
        
        for query in test_queries:
            for _ in range(iterations):
                # Measure memory before
                mem_before = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                
                # Measure response time
                start_time = time.time()
                therapy_rag_service.get_therapy_approach(query)
                end_time = time.time()
                response_time = end_time - start_time
                
                # Measure memory after
                mem_after = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                memory_used = mem_after - mem_before
                
                results["response_times"].append(response_time)
                results["memory_usage"].append(memory_used)
        
        # Calculate averages
        results["avg_response_time"] = statistics.mean(results["response_times"])
        results["avg_memory_usage"] = statistics.mean(results["memory_usage"])
        
        return results
    
    def _get_system_info(self):
        """Get system information for the benchmark"""
        import platform
        import torch
        
        info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
        }
        
        # Add GPU information if available
        try:
            if torch.cuda.is_available():
                info["gpu"] = {
                    "available": True,
                    "name": torch.cuda.get_device_name(0),
                    "count": torch.cuda.device_count(),
                }
            else:
                info["gpu"] = {"available": False}
        except:
            info["gpu"] = {"available": "unknown", "error": "Could not detect GPU"}
        
        return info
    
    def _print_summary(self, results):
        """Print a summary of benchmark results"""
        self.stdout.write("\n===== BENCHMARK SUMMARY =====")
        
        # Accuracy
        accuracy = results["accuracy"].get("accuracy", 0) * 100
        self.stdout.write(f"Accuracy: {accuracy:.1f}%")
        
        # Performance
        avg_time = results["performance"].get("avg_response_time", 0)
        self.stdout.write(f"Average response time: {avg_time:.2f} seconds")
        
        avg_memory = results["performance"].get("avg_memory_usage", 0)
        self.stdout.write(f"Average memory usage: {avg_memory:.1f} MB")
        
        # Best configuration
        if "parametric" in results:
            best_config = results["parametric"].get("best_configuration", "N/A")
            best_accuracy = results["parametric"].get("best_accuracy", 0) * 100
            self.stdout.write(f"Best configuration: {best_config} ({best_accuracy:.1f}%)")
