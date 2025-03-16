# therapist/views/client_feedback_views.py
from rest_framework import viewsets
from therapist.models.client_feedback import ClientFeedback
from therapist.serializers.client_feedback import ClientFeedbackSerializer


class ClientFeedbackViewSet(viewsets.ModelViewSet):
    queryset = ClientFeedback.objects.all()
    serializer_class = ClientFeedbackSerializer
