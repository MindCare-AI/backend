# media_handler/exceptions.py
from rest_framework.exceptions import APIException
from rest_framework import status


class MediaUploadError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Media upload failed"
    default_code = "media_upload_error"


class MediaValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Media validation failed"
    default_code = "media_validation_error"
