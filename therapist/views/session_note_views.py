# therapist/views/session_note_views.py
from rest_framework import viewsets
from therapist.models.session_note import SessionNote
from therapist.serializers.session_note import SessionNoteSerializer


class SessionNoteViewSet(viewsets.ModelViewSet):
    queryset = SessionNote.objects.all()
    serializer_class = SessionNoteSerializer
