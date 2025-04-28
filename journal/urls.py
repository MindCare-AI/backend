# journal/urls.py
from django.urls import path
from .views import JournalEntryViewSet

# Define explicit view mappings
journal_entry_list = JournalEntryViewSet.as_view({"get": "list", "post": "create"})
journal_entry_detail = JournalEntryViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

app_name = "journal"

urlpatterns = [
    path("entries/", journal_entry_list, name="journal-entry-list"),
    path("entries/<int:pk>/", journal_entry_detail, name="journal-entry-detail"),
]
