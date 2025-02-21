from django.urls import path
from . import views

urlpatterns = [
    path("chat-sessions/", views.chat_sessions_view, name="chat_sessions"),
    path("messages/", views.chat_messages_view, name="chat_messages"),
    path("interventions/", views.interventions_view, name="interventions"),
]
