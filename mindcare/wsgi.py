# mindcare/wsgi.py

import os
import logging
from django.core.wsgi import get_wsgi_application

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mindcare.settings")

# Initialize WSGI application
application = get_wsgi_application()

# Attempt to set up Ollama model
try:
    from django.core.management import call_command

    call_command("setup_ollama_model")
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to set up Ollama model: {e}")
