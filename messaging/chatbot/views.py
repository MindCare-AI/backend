from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.throttling import UserRateThrottle
from .chatbot import get_ollama_response

class ChatbotThrottle(UserRateThrottle):
    rate = '5/minute'

class ChatbotResponseView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChatbotThrottle]

    def post(self, request, *args, **kwargs):
        message = request.data.get("message", "")
        conversation_history = request.data.get("history", [])
        
        if not message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = get_ollama_response(message, conversation_history)
            return Response({"response": response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Failed to get chatbot response", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )