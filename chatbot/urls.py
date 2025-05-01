from django.urls import path
from .views import ChatbotViewSet

chatbot_list = ChatbotViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

chatbot_detail = ChatbotViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy',
})

chatbot_send_message = ChatbotViewSet.as_view({
    'post': 'send_message',
})

urlpatterns = [
    path('conversations/', chatbot_list, name='chatbot-conversation-list'),
    path('conversations/<int:pk>/', chatbot_detail, name='chatbot-conversation-detail'),
    path('conversations/<int:pk>/send_message/', chatbot_send_message, name='chatbot-send-message'),
]
