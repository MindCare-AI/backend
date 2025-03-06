from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MediaFileViewSet

router = DefaultRouter()
router.register(r"media", MediaFileViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
