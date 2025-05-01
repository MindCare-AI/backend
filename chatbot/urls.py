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

urlpatterns = [
    path('conversations/', chatbot_list, name='chatbot-conversation-list'),
    path('conversations/<uuid:pk>/', chatbot_detail, name='chatbot-conversation-detail'),
]
