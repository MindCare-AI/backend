# mindcare/settings.py

from pathlib import Path
from dotenv import load_dotenv
import os
import json
from datetime import timedelta


load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-0)cm(xhi^gtudqrk0t266=keuowd-x+cfmcrj8#k2_#dsrts&t"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Update ALLOWED_HOSTS to include 'localhost'
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "localhost:8000",
    *os.getenv("ALLOWED_HOSTS", "").split(","),
    "*",  # For development only - remove in production
]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.github",  # <-- GitHub provider enabled
    "allauth.socialaccount.providers.google",
    "rest_framework",
    "rest_framework.authtoken",
    # Custom apps
    "core",
    "auth",
    "users",
    "mood",
    "journal",
    "notifications",
    "analytics",
    "drf_spectacular",
    "media_handler",
    "corsheaders",
    "messaging",
    "channels",
    "channels_redis",
    "therapist",
    "patient",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_filters",
]

SITE_ID = 1

AUTH_USER_MODEL = "users.CustomUser"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # Must be near the top
    "allauth.account.middleware.AccountMiddleware",  # <-- Added Allauth middleware
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "notifications.middleware.NotificationSecurityMiddleware",  # <-- Added notifications security middleware
]

ROOT_URLCONF = "mindcare.urls"

ASGI_APPLICATION = "mindcare.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # Your custom directories, if any
        "APP_DIRS": True,  # This must be True
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mindcare.wsgi.application"


# Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "OPTIONS": json.loads(
            os.getenv("OPTIONS", "{}")
        ),  # Convert string to dictionary
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

REST_AUTH = {
    "REGISTER_SERIALIZER": "auth.serializers.CustomRegisterSerializer",
    "USE_JWT": True,
    "JWT_AUTH_COOKIE": "auth",
    "JWT_AUTH_REFRESH_COOKIE": "refresh-auth",
}

ACCOUNT_ADAPTER = "auth.registration.custom_adapter.CustomAccountAdapter"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

SOCIALACCOUNT_ADAPTER = "auth.registration.custom_adapter.CustomSocialAccountAdapter"

# Configure django-allauth to use email as the primary identifier
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True

# Email Configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp-relay.brevo.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "7fa9d1001@smtp-brevo.com"
EMAIL_HOST_PASSWORD = "y9Pw4DtnMFcI6Y38"
DEFAULT_FROM_EMAIL = "azizbahloulextra@gmail.com"

# Django-allauth Settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # Keep only this one
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_EMAIL_SUBJECT_PREFIX = "MindCare - "

# Remove duplicate settings and keep only this adapter
ACCOUNT_ADAPTER = "auth.registration.custom_adapter.CustomAccountAdapter"

# Social account provider settings
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "key": "",
        },
        "SCOPE": [
            "openid",  # Add OpenID Connect scope
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "offline",  # Enable refresh tokens
            "prompt": "consent",  # Force consent screen
        },
        "VERIFIED_EMAIL": True,
        "REDIRECT_URI": "mindcareai://oauth_callback",
    },
    "github": {
        "APP": {
            "client_id": os.getenv("GITHUB_CLIENT_ID"),
            "secret": os.getenv("GITHUB_CLIENT_SECRET"),
            "key": "",
        },
        "SCOPE": [
            "user",
            "user:email",
        ],
        "REDIRECT_URI": "mindcareai://oauth_callback",
    },
}

# OAuth specific settings
GOOGLE_OAUTH_SETTINGS = {
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
    "redirect_uri": "mindcareai://oauth_callback",
    "authorization_base_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
}

# Add these settings near your other OAuth/Social Auth settings
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_REDIRECT_URI = "mindcareai://oauth_callback"

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Media file size limits
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MEDIA_TYPES = {
    "image": ["image/jpeg", "image/png", "image/gif"],
    "video": ["video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo"],
    "audio": ["audio/mpeg", "audio/wav", "audio/ogg"],
    "document": [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ],
}

# Media upload settings
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MEDIA_TYPES = {
    "image": [".jpg", ".jpeg", ".png", ".gif"],
    "video": [".mp4", ".mov", ".avi"],
    "audio": [".mp3", ".wav", ".ogg"],
    "document": [".pdf", ".doc", ".docx", ".txt"],
}

MEDIA_FILE_STORAGE = {
    "max_files_per_user": 100,
    "allowed_extensions": [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".pdf", ".doc"],
    "scan_on_upload": True,
    "verify_content_type": True,
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
        "chatbot": "30/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "messaging.pagination.CustomMessagePagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MindCare API",
    "DESCRIPTION": "API documentation for MindCare application",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": True,
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayOperationId": True,
    },
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SCHEMA_COERCE_PATH_PK_SUFFIX": True,
    "POSTPROCESSING_HOOKS": [],
}

OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Allow your React Native/Web app
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8082",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://localhost:19006",  # React Native Expo default
    "http://127.0.0.1:19006",
    "http://127.0.0.1:3000",
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
]

# Allow WebSocket connections
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# WebSocket specific settings
# WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', 'ws://localhost:8000')
# WEBSOCKET_ALLOWED_ORIGINS = os.getenv('WEBSOCKET_ALLOWED_ORIGINS', '').split(',')

# JWT settings for WebSocket authentication
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_LIFETIME", 60))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_LIFETIME", 1))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": os.getenv("JWT_ALGORITHM", "HS256"),
    "SIGNING_KEY": os.getenv("JWT_SECRET_KEY", SECRET_KEY),
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
}

# Channel Layers Configuration for WebSocket
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

# Celery Configuration
REDIS_URL = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0"
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ROUTES = {
    'messaging.tasks.process_chatbot_response': {'queue': 'chatbot'}
}
CELERY_TASK_DEFAULT_QUEUE = 'default'

# Enhanced logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/email.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "channels": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
        "messaging": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
        "django.core.mail": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "allauth": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "auth.registration": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "messaging.services.chatbot": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "logs/debug.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "auth.registration": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

# Firebase configuration for hybrid SQL/NoSQL messaging
try:
    # Update the path if needed—here we assume the file is in messaging/firebase_credentials.json
    FIREBASE_CONFIG_PATH = os.getenv(
        "FIREBASE_CONFIG_PATH",
        str(BASE_DIR / "messaging" / "firebase_credentials.json"),
    )
    with open(FIREBASE_CONFIG_PATH, "r") as f:
        FIREBASE_CONFIG = json.load(f)
except Exception as e:
    print("Error loading FIREBASE_CONFIG from file:", e)
    FIREBASE_CONFIG = {}

FIREBASE_CERT_PATH = os.getenv(
    "FIREBASE_CERT_PATH", str(BASE_DIR / "firebase-cert.json")
)
FIREBASE_DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL", "https://your-firebase-database.firebaseio.com"
)

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Verification settings
VERIFICATION_SETTINGS = {
    "LICENSE_PATTERNS": [
        r"License[:\s]+([A-Z0-9-]+)",
        r"Registration[:\s]+([A-Z0-9-]+)",
    ],
    "MAX_VERIFICATION_ATTEMPTS": 3,
    "VERIFICATION_COOLDOWN_HOURS": 24,
}

# Group Conversation Settings
GROUP_SETTINGS = {
    "MAX_GROUPS_PER_USER": 10,
    "MAX_PARTICIPANTS_PER_GROUP": 50,
    "MAX_MODERATORS_PER_GROUP": 5,
    "MESSAGE_EDIT_WINDOW": 3600,  # 1 hour in seconds
    "MAX_MESSAGE_LENGTH": 5000,
}

# Group Settings
GROUP_SETTINGS = {
    "MAX_PARTICIPANTS_PER_GROUP": 50,
    "MAX_MESSAGE_LENGTH": 5000,
    "MAX_GROUP_NAME_LENGTH": 100,
    "MIN_PARTICIPANTS": 2,
    "ALLOW_MESSAGE_EDITING": True,
    "MESSAGE_EDIT_WINDOW": 3600,  # 1 hour in seconds
}

# Message Settings
MESSAGE_SETTINGS = {
    "MESSAGE_EDIT_WINDOW": 3600,  # 1 hour in seconds
    "MAX_EDIT_HISTORY": 10,  # Maximum number of previous versions to keep
    "ALLOW_MESSAGE_DELETION": True,
    "KEEP_DELETED_MESSAGES": True,  # If False, will hard delete instead of soft delete
}

# Chatbot Settings
GEMINI_API_KEY = 'AIzaSyC0kDGVJlr-vYPcYjHHSS__aLPfq2dI734'
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent'
CHATBOT_SETTINGS = {
    'MAX_RETRIES': 3,
    'RESPONSE_TIMEOUT': 30,
    'MAX_HISTORY_MESSAGES': 5,
    'MIN_MESSAGE_LENGTH': 2,
    'MAX_MESSAGE_LENGTH': 1000,
}

# Throttling Configuration
THROTTLE_RATES = {
    "message_default": "60/minute",
    "typing": "30/minute",
    "chatbot": "30/minute",
    "group_message": "100/hour",
    "one_to_one_message": "200/hour",
    "burst_message": "10/minute",
}

# User Type Specific Rates
USER_TYPE_THROTTLE_RATES = {
    "patient": "100/hour",
    "therapist": "300/hour",
    "premium_patient": "200/hour",
}

# Redis Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "db": 1,
            "socket_timeout": 5,
            "socket_connect_timeout": 5,
            "retry_on_timeout": True,
            "max_connections": 100,
        },
    }
}

# Session Configuration (if using Redis for sessions)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Registration Settings
MAX_REGISTRATION_ATTEMPTS = 5
EMAIL_VERIFICATION_TIMEOUT = 3600  # 1 hour

# Redis Connection Pool Settings
REDIS_POOL_SETTINGS = {"MAX_CONNECTIONS": 100, "TIMEOUT": 20, "RETRY_ON_TIMEOUT": True}

# User Settings Configuration
USER_SETTINGS = {
    "THEME_MODES": ["light", "dark", "system"],
    "PRIVACY_LEVELS": ["public", "private", "contacts_only"],
    "DEFAULT_THEME": {"mode": "system", "color_scheme": "default"},
    "DEFAULT_PRIVACY": {"profile_visibility": "public", "show_online_status": True},
}
