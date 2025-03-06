# messaging/views/chatbot.py
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from ..models.chatbot import ChatbotConversation, ChatbotMessage
from ..serializers.chatbot import (
    ChatbotConversationSerializer,
    ChatbotMessageSerializer
)
from messaging.services.chatbot import get_chatbot_response

class ChatbotConversationViewSet(viewsets.ModelViewSet):
    queryset = ChatbotConversation.objects.all()
    serializer_class = ChatbotConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        conv, created = ChatbotConversation.objects.get_or_create(
            user=request.user
        )
        return Response(
            self.get_serializer(conv).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        conversation = self.get_object()
        serializer = ChatbotMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_message = serializer.save(
            sender=request.user,
            conversation=conversation
        )
        
        # Convert last 3 bot messages to a list of dicts (history)
        history_qs = conversation.messages.filter(is_bot=True).order_by('-timestamp')[:3]
        history = list(history_qs.values('sender', 'content'))
        
        bot_response = get_chatbot_response(
            user_message.content,
            history
        )
        
        bot_message = ChatbotMessage.objects.create(
            content=bot_response,
            sender=None,  # Bot message; sender is null.
            conversation=conversation,
            is_bot=True
        )
        
        return Response({
            'user_message': ChatbotMessageSerializer(user_message).data,
            'bot_response': ChatbotMessageSerializer(bot_message).data
        }, status=status.HTTP_201_CREATED)
