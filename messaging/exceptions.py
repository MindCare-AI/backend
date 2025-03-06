#messaging/exceptions.py
from rest_framework.exceptions import APIException

class ChatbotException(APIException):
    status_code = 500
    default_detail = 'An error occurred while processing your chatbot request.'
    default_code = 'chatbot_error'