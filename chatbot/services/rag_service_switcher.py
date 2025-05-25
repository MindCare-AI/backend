# chatbot/services/rag_service_switcher.py
import os

# Import both implementations
from .rag.therapy_rag_service import therapy_rag_service
from .rag.therapy_rag_adapter import therapy_rag_adapter

# Decide which one to use based on environment
use_local = os.getenv("USE_LOCAL_VECTOR_STORE", "true").lower() == "true"

# Export the appropriate service
rag_service = therapy_rag_adapter if use_local else therapy_rag_service
