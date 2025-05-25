import os
from typing import Dict, Any
import logging

from django.conf import settings

from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama

logger = logging.getLogger(__name__)

def get_therapy_vectorstore():
    """Load the therapy vector store."""
    db_path = os.path.join(settings.BASE_DIR, 'rag_data', 'therapy_faiss')
    
    # Check if the vector store exists
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Therapy RAG data not found at {db_path}. "
            "Please run 'python manage.py setup_therapy_rag' first."
        )
    
    # Load the vector store with local Ollama embeddings
    embeddings = OllamaEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest"),
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    return FAISS.load_local(db_path, embeddings)

def get_therapy_qa_chain():
    """Create a QA chain for therapy questions using the RAG system."""
    vectorstore = get_therapy_vectorstore()
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}
    )
    
    # Use local Ollama model instead of OpenAI
    llm = Ollama(
        model=os.getenv("LLM_MODEL", "mistral"),
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        temperature=0.2
    )
    
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )
    
    return qa_chain

def is_therapy_question(question: str) -> bool:
    """Determine if a question is therapy-related."""
    # Simple keyword matching - could be enhanced with more sophisticated detection
    therapy_keywords = [
        "therapy", "therapist", "cbt", "dbt", "cognitive", "behavioral",
        "dialectical", "depression", "anxiety", "mental health", "counseling",
        "psychological", "psychiatrist", "mindfulness", "emotional", "trauma"
    ]
    
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in therapy_keywords)

def answer_therapy_question(question: str) -> Dict[str, Any]:
    """Answer a therapy-related question using the RAG system."""
    try:
        qa_chain = get_therapy_qa_chain()
        result = qa_chain({"query": question})
        
        return {
            "answer": result["result"],
            "sources": [doc.metadata.get("source", "Unknown") for doc in result["source_documents"]]
        }
    except Exception as e:
        logger.error(f"Error using therapy RAG: {str(e)}")
        # Fallback to direct LLM if RAG fails
        return {
            "answer": "I apologize, but I'm having trouble accessing my therapeutic knowledge database. I can still help with general guidance, but for specific therapeutic techniques, it might be best to consult a licensed therapist.",
            "sources": ["Error: RAG retrieval failed"]
        }
