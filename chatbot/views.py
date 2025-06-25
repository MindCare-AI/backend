# chatbot/views.py
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import Count
from django.db import transaction

from .models import ChatbotConversation, ChatMessage
from .serializers import (
    ChatMessageSerializer,
    ChatbotConversationSerializer,
    ChatbotConversationUpdateSerializer,
    ChatbotConversationListSerializer,
)

# Import chatbot service
from .services.chatbot_service import chatbot_service
from .utils.rag_utils import answer_therapy_question

# Use the regular chatbot service which will be modified to use local RAG
active_chatbot_service = chatbot_service

logger = logging.getLogger(__name__)


class ChatbotPagination(PageNumberPagination):
    """Custom pagination for chatbot conversations"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ChatbotViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for managing chatbot conversations and messages."""

    queryset = ChatbotConversation.objects.all()
    serializer_class = ChatbotConversationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatbotPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "metadata"]
    ordering_fields = ["created_at", "last_activity", "title"]
    ordering = ["-last_activity"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "list":
            return ChatbotConversationListSerializer
        elif self.action in ["update", "partial_update"]:
            return ChatbotConversationUpdateSerializer
        elif self.action == "send_message":
            return ChatMessageSerializer
        return ChatbotConversationSerializer

    def get_queryset(self):
        """Enhanced queryset with optimized loading and user filtering"""
        queryset = (
            ChatbotConversation.objects.filter(user=self.request.user)
            .select_related("user")
            .prefetch_related("messages")
            .annotate(message_count=Count("messages"))
        )

        # Apply time-based filters
        time_filter = self.request.query_params.get("time_filter")
        if time_filter:
            now = timezone.now()
            if time_filter == "24h":
                queryset = queryset.filter(last_activity__gte=now - timedelta(hours=24))
            elif time_filter == "7d":
                queryset = queryset.filter(last_activity__gte=now - timedelta(days=7))
            elif time_filter == "30d":
                queryset = queryset.filter(last_activity__gte=now - timedelta(days=30))

        # Filter by active status
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset

    def perform_create(self, serializer):
        """Enhanced create with proper user assignment"""
        serializer.save(user=self.request.user)

    @extend_schema(
        description="List chatbot conversations with optional filtering",
        parameters=[
            OpenApiParameter(
                name="time_filter",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by time: '24h', '7d', '30d'",
                enum=["24h", "7d", "30d"],
            ),
            OpenApiParameter(
                name="is_active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by active status",
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        """Enhanced list with proper serialization context and auto-creation"""
        queryset = self.filter_queryset(self.get_queryset())

        # When user opens the chatbot screen for the first time,
        # auto-create a welcome conversation with an introduction message.
        if not queryset.exists():
            with transaction.atomic():
                conversation = ChatbotConversation.objects.create(
                    user=request.user,
                    title="Welcome Chat",
                    metadata={"auto_created": True, "type": "welcome"},
                )
                welcome_text = (
                    "Welcome to your personal chatbot companion! We're delighted to have you here. "
                    "At our service, we strive to create an engaging and uniquely tailored experience. "
                    "To be of the utmost help, we discreetly collect information such as your conversation history, "
                    "interaction patterns, and usage details. This data is guarded under the strictest confidentiality "
                    "protocols and is treated as top secret—ensuring your privacy is never compromised. "
                    "We use these insights solely to enhance your experience and provide you with exceptional support. "
                    "Feel completely at ease; our commitment to your privacy and security stands paramount as you explore our features."
                )
                ChatMessage.objects.create(
                    conversation=conversation,
                    content=welcome_text,
                    is_bot=True,
                    message_type="system",
                )
            queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page, many=True, context={"request": request}
            )
            for conversation in serializer.data:
                # Get the last 5 messages for each conversation
                messages = ChatMessage.objects.filter(
                    conversation_id=conversation["id"]
                ).order_by("-timestamp")[:5]
                conversation["recent_messages"] = ChatMessageSerializer(
                    messages, many=True, context={"request": request}
                ).data
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        description="Retrieve a specific chatbot conversation with full details",
        responses={200: ChatbotConversationSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        """Enhanced retrieve with message history"""
        instance = self.get_object()

        # Ensure user owns this conversation
        if instance.user != request.user:
            return Response(
                {"error": "You do not have access to this conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(instance, context={"request": request})
        response_data = serializer.data

        # Add recent messages
        messages = instance.messages.all().order_by("timestamp")
        response_data["messages"] = ChatMessageSerializer(
            messages, many=True, context={"request": request}
        ).data

        return Response(response_data)

    @extend_schema(
        description="Update chatbot conversation details (title, metadata, status)",
        request=ChatbotConversationUpdateSerializer,
        responses={200: ChatbotConversationSerializer},
    )
    def update(self, request, *args, **kwargs):
        """Enhanced update with proper validation"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Ensure user owns this conversation
        if instance.user != request.user:
            return Response(
                {"error": "You do not have access to this conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            updated_instance = serializer.save()

            # Log the update
            logger.info(
                f"Conversation {updated_instance.id} updated by user {request.user.id}. "
                f"Updated fields: {list(serializer.validated_data.keys())}"
            )

        # Return the updated conversation with full details
        response_serializer = ChatbotConversationSerializer(
            updated_instance, context={"request": request}
        )
        return Response(response_serializer.data)

    @extend_schema(
        description="Partially update chatbot conversation (PATCH)",
        request=ChatbotConversationUpdateSerializer,
        responses={200: ChatbotConversationSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        """Handle partial updates (PATCH requests)"""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(
        description="Delete a chatbot conversation and all its messages",
        responses={
            204: {"description": "Conversation deleted successfully"},
            403: {"description": "Permission denied"},
            404: {"description": "Conversation not found"},
        },
    )
    def destroy(self, request, *args, **kwargs):
        """Enhanced delete with proper cleanup"""
        instance = self.get_object()

        # Ensure user owns this conversation
        if instance.user != request.user:
            return Response(
                {"error": "You do not have access to this conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            conversation_id = instance.id
            message_count = instance.messages.count()

            # Delete the conversation (messages will be cascade deleted)
            instance.delete()

            # Log the deletion
            logger.info(
                f"Conversation {conversation_id} deleted by user {request.user.id}. "
                f"Deleted {message_count} messages."
            )

        return Response(
            {
                "message": f"Conversation deleted successfully. {message_count} messages removed."
            },
            status=status.HTTP_204_NO_CONTENT,
        )

    @extend_schema(
        description="Send a message to the chatbot and get a response",
        request=ChatMessageSerializer,
        responses={201: ChatMessageSerializer},
    )
    @action(detail=True, methods=["POST"], url_path="send_message")
    def send_message(self, request, pk=None):
        """Send a message to the chatbot and get a response."""
        from django.http import Http404
        try:
            try:
                conversation = self.get_object()
            except Http404:
                return Response(
                    {"error": "Conversation not found or you do not have access."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Check if the conversation belongs to the current user
            if conversation.user != request.user:
                return Response(
                    {"error": "You do not have access to this conversation"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get the content directly from request data
            content = request.data.get("content")
            if not content or not content.strip():
                return Response(
                    {"error": "Message content is required and cannot be empty"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                # Validate and create the user's message
                message_data = {
                    "content": content.strip(),
                    "conversation": conversation.id,
                    "sender": request.user.id,
                    "is_bot": False,
                }

                message_serializer = ChatMessageSerializer(data=message_data)
                if not message_serializer.is_valid():
                    return Response(
                        message_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

                # Attach conversation FK explicitly
                user_message = message_serializer.save(conversation=conversation)

                # Get conversation history
                conversation_messages = ChatMessage.objects.filter(
                    conversation=conversation
                ).order_by("timestamp")

                # Determine if this is a therapy-related question
                def is_therapy_question(content):
                    # Simple keyword-based check; replace with your own logic as needed
                    therapy_keywords = [
                        "therapy",
                        "mental health",
                        "counseling",
                        "depression",
                        "anxiety",
                        "help",
                        "feel",
                        "stress",
                    ]
                    return any(
                        keyword in content.lower() for keyword in therapy_keywords
                    )

                if is_therapy_question(user_message.content):
                    # Use the RAG system for therapy questions
                    bot_response = answer_therapy_question(user_message.content)
                else:
                    # Get chatbot response using the active service (GPU or standard)
                    bot_response = active_chatbot_service.get_response(
                        user=request.user,
                        message=user_message.content,
                        conversation_id=str(conversation.id),
                        conversation_history=[
                            {
                                "id": msg.id,
                                "content": msg.content,
                                "is_bot": msg.is_bot,
                                "timestamp": msg.timestamp,
                            }
                            for msg in conversation_messages
                        ],
                    )

                # Ensure bot_response has required 'content' key
                if not isinstance(bot_response, dict) or "content" not in bot_response:
                    logger.error(f"Invalid bot response format: {bot_response}")
                    bot_response = {
                        "content": "I apologize, but I'm experiencing technical difficulties. Please try again later.",
                        "metadata": {"error": "Invalid response format"},
                    }

                # Create bot's response message
                bot_message_data = {
                    "content": bot_response["content"],
                    "conversation": conversation.id,
                    "sender": None,
                    "is_bot": True,
                    "metadata": bot_response.get("metadata", {}),
                }

                bot_message_serializer = ChatMessageSerializer(data=bot_message_data)
                if not bot_message_serializer.is_valid():
                    return Response(
                        bot_message_serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                bot_message = bot_message_serializer.save(conversation=conversation)

                # Update conversation's last activity
                conversation.last_activity = timezone.now()
                conversation.save(update_fields=["last_activity"])

            # Return both user message and bot response with complete serialized data
            return Response(
                {
                    "user_message": ChatMessageSerializer(
                        user_message, context={"request": request}
                    ).data,
                    "bot_response": ChatMessageSerializer(
                        bot_message, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error in chatbot message handling: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to process message", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        description="Get messages for a specific conversation with pagination",
        parameters=[
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of messages to return (default: 50)",
            ),
            OpenApiParameter(
                name="offset",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of messages to skip",
            ),
        ],
        responses={200: ChatMessageSerializer(many=True)},
    )
    @action(detail=True, methods=["GET"], url_path="messages")
    def get_messages(self, request, pk=None):
        """Get messages for a conversation with pagination"""
        conversation = self.get_object()

        # Ensure user owns this conversation
        if conversation.user != request.user:
            return Response(
                {"error": "You do not have access to this conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get pagination parameters
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))

        # Validate pagination parameters
        if limit > 200:
            limit = 200
        if limit < 1:
            limit = 1
        if offset < 0:
            offset = 0

        messages = ChatMessage.objects.filter(conversation=conversation).order_by(
            "timestamp"
        )[offset : offset + limit]

        serializer = ChatMessageSerializer(
            messages, many=True, context={"request": request}
        )

        total_messages = conversation.messages.count()

        return Response(
            {
                "messages": serializer.data,
                "total": total_messages,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_messages,
            }
        )

    @extend_schema(
        description="Archive/unarchive a conversation (set is_active status)",
        request={"type": "object", "properties": {"is_active": {"type": "boolean"}}},
        responses={200: ChatbotConversationSerializer},
    )
    @action(detail=True, methods=["POST"], url_path="toggle_active")
    def toggle_active(self, request, pk=None):
        """Toggle the active status of a conversation"""
        conversation = self.get_object()

        # Ensure user owns this conversation
        if conversation.user != request.user:
            return Response(
                {"error": "You do not have access to this conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_active = request.data.get("is_active")
        if is_active is None:
            # Toggle current status
            conversation.is_active = not conversation.is_active
        else:
            conversation.is_active = bool(is_active)

        conversation.save(update_fields=["is_active"])

        serializer = ChatbotConversationSerializer(
            conversation, context={"request": request}
        )

        action = "activated" if conversation.is_active else "archived"
        return Response(
            {
                "message": f"Conversation {action} successfully",
                "conversation": serializer.data,
            }
        )

    @extend_schema(
        methods=["GET"],
        responses={200: dict},
    )
    @action(detail=False, methods=["GET"], url_path="system-info")
    def system_info(self, request):
        """Get system information about the chatbot service."""
        try:
            # Get RAG service info
            rag_info = {
                "service_name": "Standard RAG Service",
                "vector_store_type": "PostgreSQL",
            }

            # Try to get database stats
            try:
                from django.db import connection

                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM therapy_documents")
                    doc_count = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM therapy_chunks")
                    chunk_count = cursor.fetchone()[0]
                    rag_info["document_count"] = doc_count
                    rag_info["chunk_count"] = chunk_count
            except Exception as e:
                rag_info["db_error"] = str(e)

        except Exception as e:
            rag_info = {"error": str(e)}

        return Response(
            {
                "using_gpu_service": False,
                "service_type": "Standard",
                "rag_info": rag_info,
            }
        )

    @extend_schema(
        description="Clear all messages from a conversation",
        responses={
            200: {"description": "Conversation cleared successfully"},
            403: {"description": "Permission denied"},
            404: {"description": "Conversation not found"},
        },
    )
    @action(detail=True, methods=["post"], url_path="clear")
    def clear_conversation(self, request, pk=None):
        """Clear all messages from a conversation"""
        conversation = self.get_object()

        # Ensure user owns this conversation
        if conversation.user != request.user:
            return Response(
                {"error": "You do not have access to this conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            # Count messages before deletion
            message_count = conversation.messages.count()

            # Delete all messages in the conversation
            conversation.messages.all().delete()

            # Update conversation's last activity
            conversation.last_activity = timezone.now()
            conversation.save(update_fields=["last_activity"])

            # Log the clearing
            logger.info(
                f"Conversation {conversation.id} cleared by user {request.user.id}. "
                f"Deleted {message_count} messages."
            )

        return Response(
            {
                "message": f"Conversation cleared successfully. {message_count} messages removed.",
                "conversation_id": conversation.id,
                "messages_deleted": message_count,
            },
            status=status.HTTP_200_OK,
        )
