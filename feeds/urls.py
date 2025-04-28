# feeds/urls.py
from django.urls import path
from .views import PostViewSet, CommentViewSet

app_name = "feeds"

urlpatterns = [
    # Post URLs
    path(
        "posts/",
        PostViewSet.as_view({"get": "list", "post": "create"}),
        name="post-list",
    ),
    path(
        "posts/<int:pk>/",
        PostViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="post-detail",
    ),
    # Comment URLs
    path(
        "comments/",
        CommentViewSet.as_view({"get": "list", "post": "create"}),
        name="comment-list",
    ),
    path(
        "comments/<int:pk>/",
        CommentViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="comment-detail",
    ),
    # If you have any custom actions in your ViewSets, add them like this:
    path(
        "posts/<int:pk>/like/",
        PostViewSet.as_view({"post": "like"}),
        name="post-like",
    ),
]
