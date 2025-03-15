# media_handler/permissions.py
from rest_framework import permissions


class IsUploaderOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow uploaders of a media file to edit or delete it
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the uploader
        return obj.uploaded_by == request.user
