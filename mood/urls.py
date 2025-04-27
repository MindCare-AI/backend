# mood/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from mood.views import MoodLogViewSet

router = DefaultRouter()
router.register(r'logs', MoodLogViewSet, basename='mood-log')

urlpatterns = [
    path('', include(router.urls)),
]
