from django.urls import path
from . import views

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    path("preferences/", views.preferences_view, name="preferences"),
    path("settings/", views.settings_view, name="settings"),
]
