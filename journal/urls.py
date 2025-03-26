#journal/urls.py
from django.urls import path
from journal.views import JournalEntryViewSet

urlpatterns = [
    path("entries/", JournalEntryViewSet.as_view({"get": "list", "post": "create"}), name="journal-entry-list"),
    path("entries/<int:pk>/", JournalEntryViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="journal-entry-detail"),
]
