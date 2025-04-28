# mood/urls.py
from django.urls import path
from mood.views import MoodLogViewSet

# Create view mappings for each action
mood_log_list = MoodLogViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
mood_log_detail = MoodLogViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})
analytics_view = MoodLogViewSet.as_view({'get': 'analytics'})
export_view = MoodLogViewSet.as_view({'get': 'export'})
bulk_create_view = MoodLogViewSet.as_view({'post': 'bulk_create'})

urlpatterns = [
    path("logs/", mood_log_list, name="mood-log-list"),
    path("logs/<int:pk>/", mood_log_detail, name="mood-log-detail"),
    path("logs/analytics/", analytics_view, name="mood-log-analytics"),
    path("logs/export/", export_view, name="mood-log-export"),
    path("logs/bulk_create/", bulk_create_view, name="mood-log-bulk-create"),
]
