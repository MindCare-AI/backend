# journal/urls.py
from django.urls import path
from .views import JournalEntryViewSet, JournalCategoryViewSet

# Define explicit view mappings for entries
journal_entry_list = JournalEntryViewSet.as_view({"get": "list", "post": "create"})
journal_entry_detail = JournalEntryViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

# Define explicit view mappings for categories
journal_category_list = JournalCategoryViewSet.as_view(
    {"get": "list", "post": "create"}
)
journal_category_detail = JournalCategoryViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
journal_category_entries = JournalCategoryViewSet.as_view({"get": "entries"})

app_name = "journal"

urlpatterns = [
    # Journal Category endpoints
    path("categories/", journal_category_list, name="journal-category-list"),
    path(
        "categories/<int:pk>/", journal_category_detail, name="journal-category-detail"
    ),
    path(
        "categories/<int:pk>/entries/",
        journal_category_entries,
        name="journal-category-entries",
    ),
    # Journal Entry endpoints - can include category in request body
    path("entries/", journal_entry_list, name="journal-entry-list"),
    path("entries/<int:pk>/", journal_entry_detail, name="journal-entry-detail"),
    # Existing action endpoints
    path(
        "entries/share/<str:journal_id>/",
        JournalEntryViewSet.as_view({"post": "share"}),
        name="journal-entry-share",
    ),
    path(
        "entries/statistics/",
        JournalEntryViewSet.as_view({"get": "statistics"}),
        name="journal-entry-statistics",
    ),
]
