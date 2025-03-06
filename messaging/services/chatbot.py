import os
import requests
from typing import List, Dict


def get_chatbot_response(message: str, history: List[Dict]) -> str:
    api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")

    # Build history string separately
    history_str = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in history])

    # Create prompt without using triple quotes inside f-string
    prompt = "Context: Mental health support conversation. Be empathetic, offer practical advice.\n"
    prompt += f"History:\n{history_str}\n"
    prompt += f"User: {message}\n"
    prompt += "Samantha:"

    payload = {
        "model": "samantha-mistral",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "max_tokens": 150, "repeat_penalty": 1.2},
    }

    try:
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("response", "I need a moment to think.").strip()
    except Exception:
        return "Sorry, I'm having trouble responding right now."
