# messaging/services/chatbot.py
import requests
from typing import List, Dict, Optional
import logging
from django.conf import settings
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

class ChatbotError(APIException):
    status_code = 503
    default_detail = "Chatbot service temporarily unavailable"

def get_chatbot_response(message: str, history: List[Dict]) -> str:
    """Get response from Gemini API."""
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    api_key = settings.GEMINI_API_KEY

    # Log request for debugging
    logger.debug(f"Sending request to Gemini API with message: {message}")
    
    # Build history string
    history_str = "\n".join([
        f"{msg['sender']}: {msg['content']}" 
        for msg in history[-5:]  # Only use last 5 messages
    ])

    # Create prompt
    prompt = f"""You are Samantha, a mental health support assistant. 
    Previous conversation:
    {history_str}
    User: {message}
    Samantha:"""

    try:
        response = requests.post(
            api_url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json={
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            },
            timeout=10
        )
        
        # Log response status and content for debugging
        logger.debug(f"Gemini API Response Status: {response.status_code}")
        logger.debug(f"Gemini API Response: {response.text}")

        response.raise_for_status()
        data = response.json()

        if "candidates" in data and data["candidates"]:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            logger.error("No valid response in API result")
            return "I apologize, but I'm having trouble formulating a response right now."

    except requests.exceptions.Timeout:
        logger.error("Gemini API request timed out")
        return "I'm sorry, but I'm taking too long to respond. Please try again."
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API request failed: {str(e)}")
        return "I'm having trouble connecting to my thinking process. Please try again."
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return "I encountered an unexpected error. Please try again."
