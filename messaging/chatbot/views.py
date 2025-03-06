#messaging/chatbot/views.py
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.throttling import UserRateThrottle
from .chatbot import get_ollama_response


class ChatbotThrottle(UserRateThrottle):
    rate = "5/minute"


@extend_schema_view(
    post=extend_schema(
        summary="Get Chatbot Response",
        description=(
            "Send a message to the chatbot and receive a response without creating a conversation. "
            "This endpoint is throttled to 5 requests per minute."
        ),
        request={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The user message to send to the chatbot."
                },
                "history": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Optional conversation history as an array of message objects."
                },
            },
            "required": ["message"]
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "The chatbot's response."
                    }
                },
            },
            400: {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "string",
                        "description": "Error message indicating missing or invalid input."
                    }
                },
            },
            500: {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "string",
                        "description": "Failure message indicating an error occurred while processing the request."
                    },
                    "details": {
                        "type": "string",
                        "description": "Additional details about the error."
                    },
                },
            },
        },
    )
)
class ChatbotResponseView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChatbotThrottle]

    def post(self, request, *args, **kwargs):
        message = request.data.get("message", "")
        conversation_history = request.data.get("history", [])

        if not message:
            return Response(
                {"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            response = get_ollama_response(message, conversation_history)
            return Response({"response": response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Failed to get chatbot response", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
