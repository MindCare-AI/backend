from django.contrib import admin
from .models import ChatbotConversation, ChatbotMessage

admin.site.register(ChatbotConversation)
admin.site.register(ChatbotMessage)
