# journal/views.py
from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema_view, extend_schema
from journal.models import JournalEntry
from journal.serializers import JournalEntrySerializer


@extend_schema_view(
    list=extend_schema(
        description="List all journal entries for the authenticated user.",
        summary="List Journal Entries",
        tags=["Journal"],
    ),
    retrieve=extend_schema(
        description="Retrieve a specific journal entry.",
        summary="Retrieve Journal Entry",
        tags=["Journal"],
    ),
    create=extend_schema(
        description="Create a new journal entry.",
        summary="Create Journal Entry",
        tags=["Journal"],
    ),
    update=extend_schema(
        description="Update an existing journal entry.",
        summary="Update Journal Entry",
        tags=["Journal"],
    ),
    destroy=extend_schema(
        description="Delete a journal entry.",
        summary="Delete Journal Entry",
        tags=["Journal"],
    ),
)
class JournalEntryViewSet(viewsets.ModelViewSet):
    serializer_class = JournalEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only return journal entries of the authenticated user."""
        return JournalEntry.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Associate the journal entry with the authenticated user."""
        serializer.save(user=self.request.user)
