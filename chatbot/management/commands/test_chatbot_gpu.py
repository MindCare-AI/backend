# chatbot/management/commands/test_chatbot_gpu.py
import logging
from django.core.management.base import BaseCommand
from tqdm import tqdm
import time

from chatbot.services.rag.therapy_rag_service import therapy_rag_service
from chatbot.services.rag.therapy_rag_service_gpu import therapy_rag_service_gpu
from chatbot.services.rag.gpu_utils import verify_gpu_support

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test and compare the regular and GPU-accelerated chatbot RAG services"

    def add_arguments(self, parser):
        parser.add_argument(
            "--queries",
            type=int,
            default=5,
            help="Number of test queries to run",
        )
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed query results",
        )

    def handle(self, *args, **kwargs):
        num_queries = kwargs.get("queries", 5)
        detailed = kwargs.get("detailed", False)

        # Check GPU availability
        gpu_info = verify_gpu_support()
        if gpu_info and gpu_info.get("using_gpu"):
            self.stdout.write(
                self.style.SUCCESS(f"🚀 GPU ENABLED: {gpu_info.get('details', '')}")
            )
        else:
            self.stdout.write(
                self.style.WARNING("⚠️ No GPU detected or not properly configured")
            )

        # Define test queries covering various scenarios
        test_queries = [
            "I keep having anxious thoughts about the future",
            "I struggle with emotional regulation when I'm upset",
            "I have difficulty challenging my negative thoughts",
            "I have trouble with interpersonal relationships because of my emotions",
            "I feel like I'm catastrophizing situations",
            "I need help with mindfulness practices",
            "My thoughts are spiraling out of control",
            "I get overwhelmed by emotions and can't think clearly",
            "I need help with black-and-white thinking patterns",
            "I'm working on acceptance of difficult situations",
        ]

        # Ensure we have enough queries
        if num_queries > len(test_queries):
            # Add some variations
            additional = [
                f"Help me understand why I {q.split(' I ')[-1]}" for q in test_queries
            ]
            test_queries.extend(additional)

        # Limit to requested number
        test_queries = test_queries[:num_queries]

        # Test regular service
        self.stdout.write(
            self.style.SUCCESS("\n===== Testing Standard PostgreSQL RAG =====")
        )
        if not therapy_rag_service.vector_store.loaded:
            self.stdout.write(
                self.style.ERROR("❌ PostgreSQL vector store is not loaded!")
            )

        pg_results = []
        pg_total_time = 0

        for i, query in enumerate(
            tqdm(test_queries, desc="Running PostgreSQL queries")
        ):
            start_time = time.time()
            result = therapy_rag_service.determine_therapy_approach(query)
            query_time = time.time() - start_time
            pg_total_time += query_time

            pg_results.append(
                {
                    "query": query,
                    "approach": result.get("approach", "unknown"),
                    "confidence": result.get("confidence", 0),
                    "time": query_time,
                    "chunks": len(result.get("supporting_chunks", [])),
                }
            )

            if detailed:
                self.stdout.write(f'\nQuery {i+1}: "{query}"')
                self.stdout.write(f"  - Approach: {result.get('approach', 'unknown')}")
                self.stdout.write(f"  - Confidence: {result.get('confidence', 0):.2f}")
                self.stdout.write(f"  - Time: {query_time:.3f}s")
                self.stdout.write(
                    f"  - Supporting chunks: {len(result.get('supporting_chunks', []))}"
                )

                if result.get("supporting_chunks"):
                    self.stdout.write(
                        "  - First chunk: "
                        + result["supporting_chunks"][0]["text"][:100]
                        + "..."
                    )

        # Test GPU service
        self.stdout.write(
            self.style.SUCCESS(
                "\n===== Testing GPU-Accelerated Local Vector Store ====="
            )
        )
        if not therapy_rag_service_gpu.vector_store.loaded:
            self.stdout.write(
                self.style.ERROR("❌ Local GPU vector store is not loaded!")
            )
            self.stdout.write(
                "Run 'python manage.py create_local_vector_store --force' to create it."
            )
            self.stdout.write(
                "If that's too slow, try 'python manage.py create_local_vector_store_optimized --force'"
            )
            return

        gpu_results = []
        gpu_total_time = 0

        for i, query in enumerate(
            tqdm(test_queries, desc="Running GPU-accelerated queries")
        ):
            start_time = time.time()
            result = therapy_rag_service_gpu.determine_therapy_approach(query)
            query_time = time.time() - start_time
            gpu_total_time += query_time

            gpu_results.append(
                {
                    "query": query,
                    "approach": result.get("approach", "unknown"),
                    "confidence": result.get("confidence", 0),
                    "time": query_time,
                    "chunks": len(result.get("supporting_chunks", [])),
                }
            )

            if detailed:
                self.stdout.write(f'\nQuery {i+1}: "{query}"')
                self.stdout.write(f"  - Approach: {result.get('approach', 'unknown')}")
                self.stdout.write(f"  - Confidence: {result.get('confidence', 0):.2f}")
                self.stdout.write(f"  - Time: {query_time:.3f}s")
                self.stdout.write(
                    f"  - Supporting chunks: {len(result.get('supporting_chunks', []))}"
                )

                if result.get("supporting_chunks"):
                    self.stdout.write(
                        "  - First chunk: "
                        + result["supporting_chunks"][0]["text"][:100]
                        + "..."
                    )

        # Compare results
        self.stdout.write(self.style.SUCCESS("\n===== Results Comparison ====="))
        self.stdout.write(
            f"PostgreSQL RAG average query time: {pg_total_time/len(test_queries):.3f}s"
        )
        self.stdout.write(
            f"GPU RAG average query time: {gpu_total_time/len(test_queries):.3f}s"
        )

        speedup = (pg_total_time / gpu_total_time) if gpu_total_time > 0 else 0
        self.stdout.write(f"Speed improvement: {speedup:.2f}x")

        # Compare recommendations
        matching = 0
        different_approach = []

        for i, (pg, gpu) in enumerate(zip(pg_results, gpu_results)):
            if pg["approach"] == gpu["approach"]:
                matching += 1
            else:
                different_approach.append(
                    {
                        "query": pg["query"],
                        "pg_approach": pg["approach"],
                        "pg_confidence": pg["confidence"],
                        "gpu_approach": gpu["approach"],
                        "gpu_confidence": gpu["confidence"],
                    }
                )

        accuracy = (matching / len(test_queries)) * 100
        self.stdout.write(
            f"Matching recommendations: {matching}/{len(test_queries)} ({accuracy:.1f}%)"
        )

        if different_approach:
            self.stdout.write("\nDifferent recommendations:")
            for diff in different_approach:
                self.stdout.write(f"Query: \"{diff['query']}\"")
                self.stdout.write(
                    f"  - PostgreSQL: {diff['pg_approach']} ({diff['pg_confidence']:.2f} confidence)"
                )
                self.stdout.write(
                    f"  - GPU: {diff['gpu_approach']} ({diff['gpu_confidence']:.2f} confidence)"
                )

        # Summary
        self.stdout.write(self.style.SUCCESS("\n===== Recommendation ====="))
        if gpu_total_time < pg_total_time and accuracy >= 80:
            self.stdout.write(
                self.style.SUCCESS(
                    "✅ GPU-accelerated local vector store is RECOMMENDED"
                )
            )
            self.stdout.write("    It's faster and provides similar recommendations")
            self.stdout.write("\nTo enable it, add this to your environment:")
            self.stdout.write("export USE_GPU_RAG=true")
        elif gpu_total_time < pg_total_time:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️ GPU-accelerated store is faster but has different recommendations"
                )
            )
            self.stdout.write(
                "    Review the differences to determine if they're acceptable"
            )
        else:
            self.stdout.write(
                self.style.WARNING("⚠️ PostgreSQL RAG is currently faster")
            )
            self.stdout.write(
                "    Consider optimizing your GPU setup or increasing batch size"
            )
