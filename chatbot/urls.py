# chatbot/urls.py
from django.urls import path
from .views import ChatbotViewSet

app_name = 'chatbot'

urlpatterns = [
    # Conversation CRUD operations
    path('', ChatbotViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='conversation-list'),
    
    path('<int:pk>/', ChatbotViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update', 
        'delete': 'destroy'
    }), name='conversation-detail'),
    
    # Conversation actions
    path('<int:pk>/send_message/', ChatbotViewSet.as_view({
        'post': 'send_message'
    }), name='conversation-send-message'),
    
    path('<int:pk>/messages/', ChatbotViewSet.as_view({
        'get': 'get_messages'
    }), name='conversation-messages'),
    
    path('<int:pk>/toggle_active/', ChatbotViewSet.as_view({
        'post': 'toggle_active'
    }), name='conversation-toggle-active'),
    
    path('<int:pk>/clear/', ChatbotViewSet.as_view({
        'post': 'clear_conversation'
    }), name='conversation-clear'),
    
    # System information
    path('system-info/', ChatbotViewSet.as_view({
        'get': 'system_info'
    }), name='system-info'),
]

# Example request body for the send_message endpoint
# POST request to /api/v1/chatbot/9/send_message/
# JSON body (simple format):
# {
#   "content": "Hello, can you help me with my anxiety?"
# }
#
# OR JSON body (structured format):
# {
#   "user_message": {
#     "content": "Hello, can you help me with my anxiety?"
#   }
# }
