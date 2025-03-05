import os
import requests
from typing import List, Dict, Optional


def get_ollama_response(
    message: str, conversation_history: Optional[List[Dict]] = None
) -> str:
    """
    Enhanced chatbot with context awareness
    """
    ollama_api_url = os.environ.get(
        "OLLAMA_API_URL", "http://localhost:11434/api/generate"
    )

    if not ollama_api_url:
        return "LLM configuration error. OLLAMA_API_URL not set."

    # Build context-aware prompt
    base_prompt = """You are Samantha, a compassionate mental health support assistant. 
    Your role is to provide empathetic, non-judgmental responses to users who may be struggling with mental health challenges.
    Keep your responses concise (1-2 paragraphs) and focus on offering practical advice, encouragement, or resources.
    Avoid giving medical advice or diagnosing conditions. Instead, suggest professional help when appropriate.
    Always prioritize the user's well-being and emotional safety."""

    history_context = ""
    if conversation_history:
        history_context = "\n".join(
            [
                f"User: {msg['content']}\nSamantha: {msg['response']}"
                for msg in conversation_history[-3:]
            ]  # Last 3 exchanges
        )

    full_prompt = f"{base_prompt}\n\n{history_context}\n\nUser: {message}\nSamantha:"

    payload = {
        "model": "samantha-mistral",
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,  # Controls creativity (lower = more deterministic)
            "max_tokens": 150,  # Limits response length
            "repeat_penalty": 1.2,  # Prevents repetitive responses
        },
    }

    try:
        response = requests.post(ollama_api_url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        return data.get("response", "No response from LLM.").strip()
    except requests.RequestException as e:
        print(f"Ollama API error: {str(e)}")
        return "Sorry, I need a moment to collect my thoughts. Could you please repeat that?"
