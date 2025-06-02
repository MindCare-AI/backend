# mindcare/settings.py

from pathlib import Path
from dotenv import load_dotenv
import os
import json
from datetime import timedelta


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Only load .env once, at the beginning, with explicit path
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "SECRET_KEY", "django-insecure-0)cm(xhi^gtudqrk0t266=keuowd-x+cfmcrj8#k2_#dsrts&t"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Update ALLOWED_HOSTS to be more restrictive
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    *os.getenv("ALLOWED_HOSTS", "").split(","),
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
    "django_extensions",
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
    "chatbot",
    "channels",
    "channels_redis",
    "therapist",
    "patient",
    "feeds",
    "appointments",  # Added appointments app
    "datawarehouse",  # Added datawarehouse app
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_filters",
    "AI_engine",  # Added AI_engine app
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
    "corsheaders.middleware.CorsMiddleware",
    "core.utils.RequestMiddleware",  # Place early to ensure request is available
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mindcare.urls"

ASGI_APPLICATION = "mindcare.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates", BASE_DIR / "notifications/templates"],
        "APP_DIRS": True,
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


print("DEBUG LOG: DB_HOST from .env =>", os.getenv("DB_HOST"))

BASE_DIR = Path(__file__).resolve().parent.parent

# Database Configuration with Local/Cloud Toggle
USE_CLOUD = os.getenv("USE_CLOUD", "True").lower() in ("true", "yes", "1", "t")

if USE_CLOUD:
    # Cloud Database (Neon)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT"),
            "OPTIONS": json.loads(os.getenv("OPTIONS", "{}").replace("'", '"')),
        }
    }
    print("Using CLOUD database on Neon")
else:
    # Local Database
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("LOCAL_DB_NAME", "mindcare_local"),
            "USER": os.getenv("LOCAL_DB_USER", "postgres"),
            "PASSWORD": os.getenv("LOCAL_DB_PASSWORD", "postgres"),
            "HOST": os.getenv("LOCAL_DB_HOST", "localhost"),
            "PORT": os.getenv("LOCAL_DB_PORT", "5432"),
            "OPTIONS": {},
        }
    }
    print("Using LOCAL database")


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
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "7fa9d1001@smtp-brevo.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "azizbahloulextra@gmail.com")

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

# Generate a key once and copy it here. For example:
MESSAGE_ENCRYPTION_KEY = os.environ.get(
    "MESSAGE_ENCRYPTION_KEY", "nQrchvGhEZoM462cbnZ5gZ4WpsP_M3yjD5jrW6aQ3OA="
)

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

TIME_INPUT_FORMATS = ["%H:%M"]
TIME_FORMAT = "H:i"
USE_L10N = False  # Disable localization to ensure your format is used


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Media file size limits and allowed types
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

ALLOWED_MEDIA_TYPES = {
    "image": [
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/bmp",
        "image/webp",
        "image/tiff",
        "image/svg+xml",
    ],
    "video": [
        "video/mp4",
        "video/mpeg",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-ms-wmv",
        "video/webm",
        "video/3gpp",
    ],
    "audio": [
        "audio/mpeg",
        "audio/wav",
        "audio/wave",
        "audio/x-wav",
        "audio/mp3",
        "audio/ogg",
        "audio/webm",
        "audio/aac",
        "audio/x-m4a",
    ],
    "document": [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "text/html",
        "application/json",
        "application/xml",
        "application/zip",
        "application/x-rar-compressed",
    ],
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
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/minute",
        "anon": "1000/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_CONTENT_NEGOTIATION_CLASS": "rest_framework.negotiation.DefaultContentNegotiation",
    # Note: For date-only fields (if any)
    "DATE_FORMAT": "%Y-%m-%d",
    # For time only fields
    "TIME_FORMAT": "%H:%M",
    # For date/time fields – 24-hour format
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M",
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
    "http://10.0.2.2:8000",    # Android emulator accessing Django
    "http://10.0.2.2:8081",    # React Native Metro bundler on Android emulator
    "http://localhost:8081",   # React Native Metro bundler
    "http://127.0.0.1:8081",   # React Native Metro bundler alternative
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^http://10\.0\.2\.2:\d+$",  # Android emulator IP range
    r"^http://192\.168\.\d+\.\d+:\d+$",  # Local network range
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
    "x-platform",  # Added this header to fix the CORS issue
]

# WebSocket Configuration - Updated for better stability
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://localhost:8000")
WEBSOCKET_ALLOWED_ORIGINS = os.getenv("WEBSOCKET_ALLOWED_ORIGINS", "").split(",")
WEBSOCKET_HEARTBEAT_INTERVAL = 45  # Increased from 30 to 45 seconds
WEBSOCKET_STALE_THRESHOLD = 300  # Increased from 120 to 300 seconds (5 minutes)
WEBSOCKET_CLEANUP_INTERVAL = 600  # Increased from 300 to 600 seconds (10 minutes)
WEBSOCKET_MAX_CONNECTIONS_PER_USER = 5

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
CELERY_TASK_ROUTES = {"messaging.tasks.process_chatbot_response": {"queue": "chatbot"}}
CELERY_TASK_DEFAULT_QUEUE = "default"


# Ensure logs directory exists
logs_dir = BASE_DIR / "logs"
logs_dir.mkdir(exist_ok=True)

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
            "filename": logs_dir / "email.log",
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
        "notifications": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}

# Gemini API Configuration
# Clean and normalize the API key from environment
raw_api_key = os.environ.get("GEMINI_API_KEY", "")
if isinstance(raw_api_key, str):
    GEMINI_API_KEY = raw_api_key.strip().replace('"', "").replace("'", "")
    # Check if the key seems valid (basic check)
    if len(GEMINI_API_KEY) < 10:
        print("WARNING: GEMINI_API_KEY seems too short or invalid!")
else:
    print("WARNING: GEMINI_API_KEY is not set properly!")
    GEMINI_API_KEY = ""

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
)

# Notification Cache Settings
NOTIFICATION_SETTINGS = {
    "CACHE_TIMEOUT": 3600,  # 1 hour default
    "COUNT_CACHE_TIMEOUT": 60,  # 1 minute for notification counts
    "TYPE_CACHE_TIMEOUT": 86400,  # 24 hours for notification types
    "PREFERENCES_CACHE_TIMEOUT": 3600,  # 1 hour for user preferences
    "CACHE_KEY_PREFIX": "notification",
    "MAX_CACHED_TYPES": 100,
}

# Verification settings - consolidated and enhanced
VERIFICATION_SETTINGS = {
    "MAX_VERIFICATION_ATTEMPTS": 10,  # Increased from 3 to 10
    "VERIFICATION_COOLDOWN_MINUTES": 2,  # Changed from 24 hours to 2 minutes
    "LICENSE_PATTERNS": [
        r"License[:\s]+([A-Z0-9-]+)",
        r"Registration[:\s]+([A-Z0-9-]+)",
        r"Number[:\s]+([A-Z0-9-]+)",
        r"#([A-Z0-9-]+)",
        r"Certificate[:\s]+([A-Z0-9-]+)",
        r"ID[:\s]+([A-Z0-9-]+)",
    ],
    "DATE_FORMATS": [
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%y",
        "%d/%m/%y",
    ],
    "IMAGE_REQUIREMENTS": {
        "MIN_WIDTH": 300,
        "MIN_HEIGHT": 300,
        "MAX_DIMENSION": 4000,
        "MIN_ASPECT_RATIO": 0.5,
        "MAX_ASPECT_RATIO": 2.0,
        "MAX_SIZE": 5 * 1024 * 1024,  # 5MB
        "ALLOWED_MIME_TYPES": ["image/jpeg", "image/png", "image/webp"],
    },
    "FACE_VERIFICATION": {
        "CONFIDENCE_THRESHOLD": 0.7,
        "MODEL": "VGG-Face",
        "METRIC": "cosine",
        "ENFORCE_DETECTION": True,
        "DETECTOR_BACKEND": "opencv",
    },
    "LICENSE_VALIDITY": {
        "DEFAULT_DURATION_DAYS": 365,
        "REMINDER_DAYS_BEFORE": [90, 30, 7],
        "GRACE_PERIOD_DAYS": 30,
    },
    "OCR_SETTINGS": {
        "LANGUAGES": ["en"],
        "FORCE_CPU": False,  # Set to True to always use CPU
        "GPU_MEMORY_LIMIT": 2048,  # Limit GPU memory usage (in MB)
        "CONFIDENCE_THRESHOLD": 0.7,
    },
    "LICENSE_VALIDATION": {
        "MIN_CONFIDENCE": 0.7,
        "REQUIRED_FIELDS": ["license_number", "issuing_authority", "expiry_date"],
        "ALLOWED_AUTHORITIES": [
            "State Medical Board",
            "State Board of Psychology",
            "State Board of Behavioral Sciences",
            "State Mental Health Board",
            "Board of Professional Counselors",
            "National Board for Certified Counselors",
            "American Psychological Association",
        ],
    },
}

GROUP_SETTINGS = {
    "MAX_GROUPS_PER_USER": 10,
    "MAX_PARTICIPANTS_PER_GROUP": 50,
    "MAX_MODERATORS_PER_GROUP": 5,
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
CHATBOT_SETTINGS = {
    "RESPONSE_TIMEOUT": 30,  # seconds
    "MAX_RETRIES": 3,
    "MAX_TOKENS": 1024,
    "TEMPERATURE": 0.7,
    "MODEL": "gemini-2.0-flash",
}

# Crisis Response Configuration
CRISIS_RESPONSE_SETTINGS = {
    "EMERGENCY_NUMBER": "911",  # US emergency number (customize by region)
    "CRISIS_TEXT_LINE": "Text HOME to 741741",
    "SUICIDE_PREVENTION_LIFELINE": "1-800-273-8255",
    "INTERNATIONAL_RESOURCES": {
        "US": {"hotline": "1-800-273-8255", "text": "Text HOME to 741741"},
        "UK": {"hotline": "116 123", "text": "Text SHOUT to 85258"},
        "Canada": {"hotline": "1-833-456-4566", "text": "Text HOME to 686868"},
        # Add more countries as needed
    },
    "OVERRIDE_NORMAL_FLOW": True,
    "ALERT_STAFF": True,
    "MIN_CRISIS_CONFIDENCE": 0.6,
    "HIGH_PRIORITY_KEYWORDS": [
        "kill myself",
        "suicide",
        "end my life",
        "die",
        "hurt myself",
    ],
}

CHATBOT_JOURNAL_LIMIT = 5  # Number of recent journal entries to include
CHATBOT_MOOD_LIMIT = 10  # Number of recent mood logs to include
CHATBOT_LOOKBACK_DAYS = 30  # Days to look back for user data

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
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
    "messaging": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}

# Cache timeouts for different types of data
MESSAGE_CACHE_TIMEOUT = 3600  # 1 hour for messages
CONVERSATION_CACHE_TIMEOUT = 1800  # 30 minutes for conversations
CHATBOT_CACHE_TIMEOUT = 900  # 15 minutes for chatbot responses
REACTIONS_CACHE_TIMEOUT = 3600  # 1 hour for reactions

# Bulk operations settings
MESSAGE_BULK_CACHE_SIZE = 100  # Maximum number of messages to cache per conversation

# Use Redis for session backend as well
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Cache middleware settings
CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 3600
CACHE_MIDDLEWARE_KEY_PREFIX = "mindcare"

# Cache time to live is 15 minutes
CACHE_TTL = 60 * 15

# Cache key settings
CACHE_KEY_PREFIX = "mindcare"

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
    "DEFAULT_THEME": {"mode": "SYSTEM", "color_scheme": "blue"},
    "DEFAULT_PRIVACY": {"profile_visibility": "PUBLIC", "show_online_status": True},
}

# WebSocket URL config
WEBSOCKET_URL = "/ws/"
WEBSOCKET_CONNECT_TIMEOUT = 10

# WebSocket Rate Limiting
WS_RATE_LIMIT_COUNT = 5  # Max number of messages per time period
WS_RATE_LIMIT_PERIOD = 1  # Time period in seconds
WS_MESSAGE_TYPES = {
    "message_created": "New messages sent by users",
    "message_updated": "Updates to existing messages",
    "message_deleted": "Message deletion events",
    "typing_indicator": "User typing indicators",
    "read_receipt": "Message read receipts",
    "presence_update": "Online/offline status updates",
    "conversation_updated": "Changes to conversation metadata",
}

# AI and Ollama Settings
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

CHATBOT_SETTINGS = {
    "MAX_RETRIES": 3,
    "RESPONSE_TIMEOUT": 30,
    "MAX_HISTORY_MESSAGES": 5,
}

AI_ENGINE_SETTINGS = {
    "ANALYSIS_BATCH_SIZE": 100,
    "MAX_ANALYSIS_PERIOD": 90,  # Maximum days to analyze
    "MIN_DATA_POINTS": 5,  # Minimum data points needed for analysis
    "RISK_THRESHOLD": 0.7,  # Threshold for risk alerts
    "UPDATE_FREQUENCY": 24,  # Hours between updates
    "ENABLED_MODELS": ["sentiment", "topic", "risk"],
    "CACHE_TIMEOUT": 3600,  # 1 hour cache for AI results
}
