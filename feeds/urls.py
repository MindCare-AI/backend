# feeds/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from feeds.views import (
    TopicViewSet, 
    PostViewSet,
    CommentViewSet,
    SearchViewSet,
    UserProfileViewSet
)

router = DefaultRouter()
router.register(r'topics', TopicViewSet)
router.register(r'posts', PostViewSet)
router.register(r'comments', CommentViewSet)
router.register(r'search', SearchViewSet, basename='search')
router.register(r'profiles', UserProfileViewSet, basename='profile')

urlpatterns = [
    path('', include(router.urls)),
]