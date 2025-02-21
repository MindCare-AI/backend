from django.urls import path
from . import views

urlpatterns = [
    path("anonymous-posts/", views.anonymous_posts_view, name="anonymous_posts"),
    path("support-threads/", views.support_threads_view, name="support_threads"),
    path("shared-stories/", views.shared_stories_view, name="shared_stories"),
]
