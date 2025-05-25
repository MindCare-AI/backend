# chatbot/management/commands/test_chatbot.py
import os
import time
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from chatbot.services.rag_service_switcher import rag_service
from chatbot.services.chatbot_service import chatbot_service

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test the chatbot service with various test cases"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Only check configuration without running tests",
        )
        parser.add_argument(
            "--query",
            type=str,
            help="Run a specific query instead of predefined tests",
        )

    def handle(self, *args, **kwargs):
        check_only = kwargs.get("check_only", False)
        
        # Check configuration
        self.stdout.write("Checking chatbot configuration...")
        
        # Check which vector store is being used
        use_local = os.getenv("USE_LOCAL_VECTOR_STORE", "true").lower() == "true"
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Using {'local file-based' if use_local else 'PostgreSQL'} vector store"
            )
        )
        
        # Check vector store status
        if use_local:
            from chatbot.services.rag.local_vector_store import local_vector_store
            
            if local_vector_store.loaded:
                doc_count = len(local_vector_store.documents) if hasattr(local_vector_store, 'documents') else 0
                cbt_count = len(local_vector_store.cbt_chunks) if hasattr(local_vector_store, 'cbt_chunks') else 0
                dbt_count = len(local_vector_store.dbt_chunks) if hasattr(local_vector_store, 'dbt_chunks') else 0
                
                if doc_count > 0 and (cbt_count > 0 or dbt_count > 0):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Local vector store loaded: {doc_count} docs, {cbt_count} CBT chunks, {dbt_count} DBT chunks"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING("⚠️ Local vector store loaded but no content found")
                    )
            else:
                self.stdout.write(
                    self.style.ERROR("✗ Local vector store not loaded")
                )
                return
        else:
            # Check PostgreSQL vector store
            from chatbot.services.rag.vector_store import vector_store
            from django.db import connection
            
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM therapy_documents")
                    doc_count = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM therapy_chunks")
                    chunk_count = cursor.fetchone()[0]
                    
                    if doc_count > 0 and chunk_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ PostgreSQL vector store ready: {doc_count} docs, {chunk_count} chunks"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING("⚠️ PostgreSQL vector store empty")
                        )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ PostgreSQL vector store error: {str(e)}")
                )
        
        if check_only:
            return
            
        # Check if we have a specific query to test
        specific_query = kwargs.get("query")
        
        if specific_query:
            test_cases = [specific_query]
            self.stdout.write(f"\nRunning chatbot test with query: {specific_query}")
        else:
            # Run predefined tests
            self.stdout.write("\nRunning chatbot tests:")
            
            test_cases = [
                "I've been feeling overwhelmed lately and can't seem to focus.",
                "I have trouble controlling my emotions, especially when I'm angry.",
                "I keep thinking about past mistakes and can't let them go.",
                "I struggle with setting boundaries with my family members.",
                "I'm experiencing intense emotions that feel out of control.",
            ]
        
        # Try to get a test user
        try:
            user = User.objects.first()
        except Exception:
            user = None
        
        # Create or get a test conversation for the chatbot service
        test_conversation_id = None
        if user:
            try:
                from chatbot.models import ChatbotConversation
                # Try to get or create a test conversation
                test_conversation, created = ChatbotConversation.objects.get_or_create(
                    user=user,
                    title="Test Conversation",
                    defaults={"metadata": {"test": True}}
                )
                test_conversation_id = test_conversation.id
                if created:
                    self.stdout.write(f"Created test conversation with ID: {test_conversation_id}")
                else:
                    self.stdout.write(f"Using existing test conversation with ID: {test_conversation_id}")
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"Could not create test conversation: {str(e)}")
                )
        
        for i, test_case in enumerate(test_cases):
            self.stdout.write(f"\nTest {i+1}/{len(test_cases)}: {test_case}")
            start_time = time.time()
            
            try:
                # Test RAG service first
                rag_response = rag_service.get_therapy_approach(test_case)
                
                self.stdout.write("RAG Response:")
                self.stdout.write(f"- Approach: {rag_response.get('recommended_approach', 'unknown')}")
                self.stdout.write(f"- Confidence: {rag_response.get('confidence', 0):.2f}")
                
                # Test chatbot service if we have a user and conversation
                if user and test_conversation_id:
                    chatbot_response = chatbot_service.get_response(
                        user=user,
                        message=test_case,
                        conversation_id=str(test_conversation_id),  # Use the real conversation ID
                        conversation_history=[]
                    )
                    
                    self.stdout.write(f"Chatbot Response Length: {len(chatbot_response.get('content', ''))}")
                    if len(chatbot_response.get('content', '')) > 100:
                        self.stdout.write(f"Preview: {chatbot_response['content'][:100]}...")
                    else:
                        self.stdout.write(f"Content: {chatbot_response.get('content', '')}")
                elif user:
                    # Test with RAG only if no conversation available
                    self.stdout.write("Testing RAG service only (no conversation ID)")
                    self.stdout.write(f"RAG service working: {bool(rag_response.get('recommended_approach'))}")
                else:
                    self.stdout.write("No user available for chatbot testing")
                
                elapsed = time.time() - start_time
                self.stdout.write(f"✓ Completed in {elapsed:.2f}s")
                
            except Exception as e:
                elapsed = time.time() - start_time
                self.stdout.write(
                    self.style.ERROR(f"✗ Error after {elapsed:.2f}s: {str(e)}")
                )
                logger.error(f"Test error: {str(e)}", exc_info=True)
        
        self.stdout.write(self.style.SUCCESS("\nChatbot tests completed"))
