import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from chatbot.services.rag.local_vector_store import local_vector_store


class Command(BaseCommand):
    help = "Check RAG system status and determine if retraining is needed"

    def handle(self, *args, **kwargs):
        chunks_dir = os.path.join(settings.BASE_DIR, "chatbot", "data", "chunks")
        index_dir = os.path.join(settings.BASE_DIR, "chatbot", "data", "indexed")

        # Check if vector store exists
        if not os.path.exists(chunks_dir):
            self.stdout.write(self.style.ERROR("❌ Vector store not found"))
            self.stdout.write(
                self.style.SUCCESS("YES - You need to train the RAG system")
            )
            return

        # Check if indexed documents exist
        if not os.path.exists(index_dir):
            self.stdout.write(self.style.ERROR("❌ No indexed documents found"))
            self.stdout.write(
                self.style.SUCCESS("YES - You need to train the RAG system")
            )
            return

        # Check vector store loading
        if not local_vector_store.loaded:
            self.stdout.write(self.style.ERROR("❌ Vector store failed to load"))
            self.stdout.write(
                self.style.SUCCESS("YES - You need to retrain the RAG system")
            )
            return

        # Check configuration
        config_path = os.path.join(chunks_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                self.stdout.write("✅ Vector store loaded successfully")
                self.stdout.write(
                    f"   - CBT chunks: {len(local_vector_store.cbt_chunks)}"
                )
                self.stdout.write(
                    f"   - DBT chunks: {len(local_vector_store.dbt_chunks)}"
                )
                self.stdout.write(
                    f"   - Created: {config.get('created_at', 'unknown')}"
                )
                self.stdout.write(
                    f"   - GPU enabled: {config.get('gpu_enabled', False)}"
                )

        # Test embedding generation
        try:
            test_embedding = local_vector_store.generate_embedding("test query")
            if test_embedding and len(test_embedding) > 0:
                self.stdout.write("✅ Embedding generation working")
            else:
                self.stdout.write(self.style.ERROR("❌ Embedding generation failed"))
                self.stdout.write(
                    self.style.SUCCESS("YES - You need to retrain the RAG system")
                )
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Embedding test failed: {str(e)}"))
            self.stdout.write(
                self.style.SUCCESS("YES - You need to retrain the RAG system")
            )
            return

        # Test similarity search
        try:
            results = local_vector_store.search_similar_chunks(
                "anxiety and stress", limit=3
            )
            if results and len(results) > 0:
                self.stdout.write(
                    f"✅ Similarity search working ({len(results)} results)"
                )
                for i, result in enumerate(results[:2]):
                    self.stdout.write(
                        f"   - Result {i+1}: {result['similarity']:.3f} similarity"
                    )
            else:
                self.stdout.write(
                    self.style.WARNING("⚠️ Similarity search returned no results")
                )
                self.stdout.write(
                    self.style.SUCCESS("MAYBE - Consider retraining for better results")
                )
                return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Similarity search failed: {str(e)}")
            )
            self.stdout.write(
                self.style.SUCCESS("YES - You need to retrain the RAG system")
            )
            return

        self.stdout.write(
            self.style.SUCCESS("✅ RAG system appears to be working properly")
        )
        self.stdout.write(
            self.style.SUCCESS("NO - No need to retrain unless you have new documents")
        )
