# media_handler/urls.py
from django.urls import path
from .views import MediaFileViewSet

urlpatterns = [
    path(
        "media/",
        MediaFileViewSet.as_view({
            "get": "list",
            "post": "create"
        }),
        name="media-list",
    ),
    path(
        "media/<int:pk>/",
        MediaFileViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy"
        }),
        name="media-detail",
    ),
]
