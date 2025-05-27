import os
from typing import Dict, Any
import logging
import requests

from django.conf import settings
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

logger = logging.getLogger(__name__)


def get_therapy_vectorstore():
    """Load the therapy vector store."""
    db_path = os.path.join(settings.BASE_DIR, "rag_data", "therapy_faiss")

    # Check if the vector store exists
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Therapy RAG data not found at {db_path}. "
            "Please run 'python manage.py setup_therapy_rag' first."
        )

    # Load the vector store with local Ollama embeddings
    embeddings = OllamaEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest"),
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    )
    return FAISS.load_local(db_path, embeddings)


def get_therapy_qa_chain():
    """Create a QA chain for therapy questions using the RAG system."""
    vectorstore = get_therapy_vectorstore()
    retriever = vectorstore.as_retriever(
        search_type="similarity", search_kwargs={"k": 5}
    )

    # Use local Ollama model instead of OpenAI
    llm = Ollama(
        model=os.getenv("LLM_MODEL", "mistral"),
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        temperature=0.2,
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True
    )

    return qa_chain


def is_therapy_question(question: str) -> bool:
    """Determine if a question is therapy-related."""
    # Simple keyword matching - could be enhanced with more sophisticated detection
    therapy_keywords = [
        "therapy",
        "therapist",
        "cbt",
        "dbt",
        "cognitive",
        "behavioral",
        "dialectical",
        "depression",
        "anxiety",
        "mental health",
        "counseling",
        "psychological",
        "psychiatrist",
        "mindfulness",
        "emotional",
        "trauma",
    ]

    question_lower = question.lower()
    return any(keyword in question_lower for keyword in therapy_keywords)


def answer_therapy_question(question: str) -> Dict[str, Any]:
    """
    Answer therapy-related questions using the local RAG system with improved accuracy.
    """
    try:
        # Import here to avoid circular imports
        from chatbot.services.rag.local_vector_store import local_vector_store
        from chatbot.services.rag.fallback_classifier import therapy_classifier

        # Check if vector store is loaded
        if not local_vector_store.loaded:
            logger.error("Local vector store is not loaded")
            return _create_fallback_response(
                "I'm currently having trouble accessing my therapy knowledge base. "
                "However, I'm here to help you. Could you tell me more about what's on your mind?",
                error="Vector store not loaded",
            )

        # Use a hybrid approach: combine vector similarity with keyword classification
        therapy_type, confidence, relevant_chunks = local_vector_store.determine_therapy_approach(question)
        
        # Get classification from fallback classifier as well
        classified_type, classified_confidence, explanation = therapy_classifier.classify(question)
        
        # If vector confidence is low but classifier confidence is high, use classifier result
        if confidence < 0.6 and classified_confidence > 0.7:
            therapy_type = classified_type
            confidence = classified_confidence
            logger.info(f"Using classifier recommendation: {therapy_type} ({confidence:.2f}) over vector recommendation")
        
        # If both are confident but disagree, weigh them
        elif confidence > 0.6 and classified_confidence > 0.6 and therapy_type != classified_type:
            # Use the one with higher confidence
            if classified_confidence > confidence + 0.1:  # Significant difference
                therapy_type = classified_type
                confidence = classified_confidence
                logger.info(f"Classifier recommendation {classified_type} ({classified_confidence:.2f}) overrides vector recommendation {therapy_type} ({confidence:.2f})")
        
        # Enhanced logging of decision process
        logger.info(f"Final therapy approach: {therapy_type} (confidence: {confidence:.2f})")
        logger.info(f"Vector recommended: {therapy_type} ({confidence:.2f}), Classifier recommended: {classified_type} ({classified_confidence:.2f})")

        # If confidence still too low, provide general support
        if confidence < 0.5 or therapy_type == "unknown":
            return _create_general_support_response(question)

        # Get relevant context from chunks
        if not relevant_chunks:
            return _create_general_support_response(question)

        # Use the top chunks to create context - prioritize highest similarity chunks
        context_chunks = relevant_chunks[:3]  # Use top 3 most relevant chunks

        # Build context from relevant chunks
        context = "\n\n".join(
            [
                f"From {chunk['therapy_type'].upper()} therapy: {chunk['text']}"
                for chunk in context_chunks
            ]
        )

        # Generate response using Ollama with the context
        response = _generate_therapy_response_with_context(
            question, context, therapy_type
        )

        return {
            "content": response,
            "metadata": {
                "therapy_recommendation": {
                    "approach": therapy_type,
                    "confidence": confidence,
                    "relevant_chunks": len(relevant_chunks),
                    "context_used": len(context_chunks),
                    "classifier_match": therapy_type == classified_type,
                    "classification_explanation": explanation if classified_type == therapy_type else None,
                },
                "rag_used": True,
                "fallback": False,
            },
        }

    except Exception as e:
        logger.error(f"Error in RAG therapy question answering: {str(e)}")
        return _create_fallback_response(
            "I'm experiencing some technical difficulties right now, but I'm still here to help. "
            "Could you tell me more about what's bothering you? I can offer general support and coping strategies.",
            error=str(e),
        )


def _generate_therapy_response_with_context(
    question: str, context: str, therapy_type: str
) -> str:
    """Generate a therapy response using Ollama with relevant context."""
    try:
        ollama_host = settings.OLLAMA_URL or "http://localhost:11434"
        model = "mistral"

        prompt = f"""You are a compassionate AI therapy assistant. A user has asked: "{question}"

Based on the following {therapy_type.upper()} therapy context, provide a helpful, supportive response:

{context}

Guidelines:
- Be empathetic and understanding
- Provide practical, evidence-based advice
- Use {therapy_type.upper()} therapy principles when appropriate
- Keep the response concise but meaningful (2-3 paragraphs)
- Always remind the user that you're an AI and suggest professional help for serious concerns
- Focus on the user's immediate needs and feelings

Response:"""

        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 500},
            },
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            generated_text = result.get("response", "").strip()

            if generated_text:
                return generated_text
            else:
                logger.error("Empty response from Ollama")
                return _get_fallback_therapy_response(therapy_type)
        else:
            logger.error(f"Ollama request failed: {response.status_code}")
            return _get_fallback_therapy_response(therapy_type)

    except Exception as e:
        logger.error(f"Error generating therapy response: {str(e)}")
        return _get_fallback_therapy_response(therapy_type)


def _create_general_support_response(question: str) -> Dict[str, Any]:
    """Create a general supportive response when specific therapy knowledge isn't available."""

    # Basic keyword-based responses for common themes
    question_lower = question.lower()

    if any(
        word in question_lower for word in ["anxiety", "anxious", "worried", "stress"]
    ):
        content = (
            "I understand you're dealing with anxiety or stress. These feelings are very common and valid. "
            "Here are some techniques that might help: try deep breathing exercises (breathe in for 4 counts, "
            "hold for 4, breathe out for 6), practice grounding techniques like naming 5 things you can see, "
            "4 things you can touch, 3 things you can hear, 2 things you can smell, and 1 thing you can taste. "
            "Remember, it's important to reach out to a mental health professional if these feelings persist or interfere with your daily life."
        )
    elif any(
        word in question_lower for word in ["depression", "depressed", "sad", "down"]
    ):
        content = (
            "I hear that you're struggling with difficult emotions. Depression and sadness can feel overwhelming, "
            "but please know that you're not alone and these feelings can improve. Consider establishing small daily routines, "
            "connecting with supportive people in your life, and engaging in activities that used to bring you joy, even if briefly. "
            "Professional support from a therapist or counselor can be incredibly helpful in working through these feelings."
        )
    elif any(
        word in question_lower
        for word in ["relationship", "partner", "friend", "family"]
    ):
        content = (
            "Relationship challenges are a common part of life, and it's natural to seek guidance. "
            "Effective communication, setting healthy boundaries, and practicing empathy are key foundations. "
            "Consider having honest conversations about your needs and feelings, and remember that healthy relationships "
            "require effort from all parties involved. A couples or family therapist can provide valuable tools and strategies."
        )
    else:
        content = (
            "Thank you for sharing with me. Whatever you're going through, your feelings are valid and important. "
            "While I can offer general support and coping strategies, I encourage you to speak with a mental health "
            "professional who can provide personalized guidance for your specific situation. In the meantime, "
            "practicing self-care, staying connected with supportive people, and being patient with yourself can be helpful."
        )

    return {
        "content": content,
        "metadata": {
            "therapy_recommendation": {
                "approach": "general_support",
                "confidence": 0.7,
                "relevant_chunks": 0,
                "context_used": 0,
            },
            "rag_used": False,
            "fallback": False,
        },
    }


def _get_fallback_therapy_response(therapy_type: str = "general") -> str:
    """Get a fallback response when AI generation fails."""

    if therapy_type == "cbt":
        return (
            "I understand you're looking for support. Cognitive Behavioral Therapy techniques can be helpful - "
            "try to notice your thoughts and feelings, and consider whether there might be different ways to think about the situation. "
            "Remember that thoughts, feelings, and behaviors are all connected. I'd recommend speaking with a qualified therapist "
            "who can guide you through specific CBT techniques tailored to your needs."
        )
    elif therapy_type == "dbt":
        return (
            "I hear that you're seeking help. Dialectical Behavior Therapy focuses on building skills for managing emotions "
            "and relationships. Try practicing mindfulness - focusing on the present moment without judgment. "
            "When emotions feel intense, remember that all feelings are temporary. A trained DBT therapist can teach you "
            "specific skills for distress tolerance and emotion regulation."
        )
    else:
        return (
            "I'm here to support you. While I'm having some technical difficulties accessing specific therapeutic content, "
            "I want you to know that seeking help is a positive step. Consider practicing self-care, reaching out to trusted "
            "friends or family, and connecting with a mental health professional who can provide the personalized support you deserve."
        )


def _create_fallback_response(message: str, error: str = None) -> Dict[str, Any]:
    """Create a fallback response with error metadata."""
    return {
        "content": message,
        "metadata": {
            "error": error if error else "Technical difficulties",
            "rag_used": False,
            "fallback": True,
            "therapy_recommendation": {
                "approach": "general_support",
                "confidence": 0.3,
                "relevant_chunks": 0,
                "context_used": 0,
            },
        },
    }


def test_rag_system() -> Dict[str, Any]:
    """Test the RAG system functionality."""
    try:
        from chatbot.services.rag.local_vector_store import local_vector_store

        # Test if vector store is loaded
        if not local_vector_store.loaded:
            return {
                "status": "error",
                "message": "Vector store not loaded",
                "loaded": False,
            }

        # Test embedding generation
        test_embedding = local_vector_store.generate_embedding("test anxiety question")
        if not test_embedding or all(x == 0 for x in test_embedding):
            return {
                "status": "error",
                "message": "Embedding generation failed",
                "loaded": True,
                "embedding_working": False,
            }

        # Test similarity search
        results = local_vector_store.search_similar_chunks("I feel anxious", limit=3)

        return {
            "status": "success",
            "message": "RAG system is working",
            "loaded": True,
            "embedding_working": True,
            "cbt_chunks": len(local_vector_store.cbt_chunks),
            "dbt_chunks": len(local_vector_store.dbt_chunks),
            "test_results": len(results),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"RAG system test failed: {str(e)}",
            "loaded": False,
            "error": str(e),
        }
