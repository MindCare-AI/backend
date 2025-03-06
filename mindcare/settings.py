# mindcare/settings.py

from pathlib import Path
from dotenv import load_dotenv
import os
import json
from datetime import timedelta
import redis


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
    '*',  # For development only - remove in production
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
    "therapy",
    "community",
    "activities",
    "notifications",
    "analytics",
    "drf_spectacular",
    "media_handler",
    "corsheaders",
    "messaging",
    "channels",
    "channels_redis",
]

SITE_ID = 1

# Use your custom user model to prevent clashes with django.contrib.auth.User
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
]

ROOT_URLCONF = "mindcare.urls"

ASGI_APPLICATION = "mindcare.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
    "LOGIN_SERIALIZER": "dj_rest_auth.serializers.LoginSerializer",
    "TOKEN_SERIALIZER": "dj_rest_auth.serializers.TokenSerializer",
    "JWT_SERIALIZER": "dj_rest_auth.serializers.JWTSerializer",
    "JWT_SERIALIZER_WITH_EXPIRATION": "dj_rest_auth.serializers.JWTSerializerWithExpiration",
    "JWT_TOKEN_CLAIMS_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",
    "USER_DETAILS_SERIALIZER": "auth.serializers.CustomUserDetailsSerializer",
    "PASSWORD_RESET_SERIALIZER": "dj_rest_auth.serializers.PasswordResetSerializer",
    "PASSWORD_RESET_CONFIRM_SERIALIZER": "auth.serializers.CustomPasswordResetConfirmSerializer",
    "PASSWORD_CHANGE_SERIALIZER": "dj_rest_auth.serializers.PasswordChangeSerializer",
    "REGISTER_SERIALIZER": "auth.registration.serializers.CustomRegisterSerializer",
    "REGISTER_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "TOKEN_MODEL": "rest_framework.authtoken.models.Token",
    "TOKEN_CREATOR": "dj_rest_auth.utils.default_create_token",
    "PASSWORD_RESET_USE_SITES_DOMAIN": False,
    "OLD_PASSWORD_FIELD_ENABLED": True,
    "LOGOUT_ON_PASSWORD_CHANGE": False,
    "SESSION_LOGIN": True,
    "USE_JWT": True,
    "JWT_AUTH_COOKIE": "access_token",
    "JWT_AUTH_RETURN_REFRESH": True,
    "JWT_AUTH_REFRESH_COOKIE": "refresh_token",
    "JWT_AUTH_REFRESH_COOKIE_PATH": "/",
    "JWT_AUTH_SECURE": False,  # Set to True in production to enable secure cookies
    "JWT_AUTH_HTTPONLY": True,  # prevent client side javascript from reading the cookie
    "JWT_AUTH_SAMESITE": "Lax",
    "JWT_AUTH_RETURN_EXPIRATION": False,
    "JWT_AUTH_COOKIE_USE_CSRF": True,
    "JWT_AUTH_COOKIE_ENFORCE_CSRF_ON_UNAUTHENTICATED": False,
}

ACCOUNT_ADAPTER = "auth.registration.custom_adapter.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "auth.registration.custom_adapter.CustomSocialAccountAdapter"

# Configure django-allauth to use email as the primary identifier
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True

# Email configuration to use Brevo's SMTP server
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("BREVO_EMAIL_HOST_USER", "86ca57001@smtp-brevo.com")
EMAIL_HOST_PASSWORD = os.getenv("BREVO_EMAIL_HOST_PASSWORD", "7ZgxAkWBR5G9bLds")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "azizbahloulextra@gmail.com")

# Allauth settings for email verification
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_REQUIRED = True

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
MAX_UPLOAD_SIZE = 5242880  # 5MB
ALLOWED_MEDIA_TYPES = {
    "image": ["image/jpeg", "image/png", "image/gif"],
    "video": ["video/mp4", "video/mpeg"],
    "audio": ["audio/mpeg", "audio/wav"],
    "document": ["application/pdf", "application/msword"],
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
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME', 60))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME', 1))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': os.getenv('JWT_ALGORITHM', 'HS256'),
    'SIGNING_KEY': os.getenv('JWT_SECRET_KEY', SECRET_KEY),
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
}

# Channel Layers Configuration for WebSocket
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0"],
#             "capacity": 1500,
#             "expiry": 10,
#         },
#     },
# }
# CHANNEL_LAYERS_MAX_CONNECTIONS = 1000
# CHANNEL_LAYERS_CAPACITY = 100

# Celery Configuration
REDIS_URL = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0"
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Logging configuration for WebSocket debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'channels': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'messaging': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}

# Firebase configuration for hybrid SQL/NoSQL messaging
try:
    # Update the path if needed—here we assume the file is in messaging/firebase_credentials.json
    FIREBASE_CONFIG_PATH = os.getenv("FIREBASE_CONFIG_PATH", str(BASE_DIR / "messaging" / "firebase_credentials.json"))
    with open(FIREBASE_CONFIG_PATH, "r") as f:
        FIREBASE_CONFIG = json.load(f)
except Exception as e:
    print("Error loading FIREBASE_CONFIG from file:", e)
    FIREBASE_CONFIG = {}

FIREBASE_CERT_PATH = os.getenv("FIREBASE_CERT_PATH", str(BASE_DIR / "firebase-cert.json"))
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://your-firebase-database.firebaseio.com")
