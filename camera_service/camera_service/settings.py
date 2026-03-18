"""Camera Service Settings - Dedicated RTSP streaming service"""
from pathlib import Path
import os
import sys

# Add parent directory to path to access main project's database
BASE_DIR = Path(__file__).resolve().parent.parent
MAIN_PROJECT_DIR = BASE_DIR.parent

sys.path.insert(0, str(MAIN_PROJECT_DIR))

SECRET_KEY = 'camera-service-key-change-in-production'
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '10.17.2.47', '*']

# Disable SSL redirect for development (enable in production)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [
    'https://localhost',
    'https://localhost:8443',
    'https://127.0.0.1',
    'https://127.0.0.1:8443',
    'https://10.17.2.47',
    'https://10.17.2.47:8443',
]
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_HSTS_SECONDS = 0

SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CONTENT_TYPE_NOSNIFF = True

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'corsheaders',
    'cameras',  # Need Camera model
    'mobile_cameras',  # Need MobileCamera model
    'accounts',  # Need UserProfile model for mobile camera permissions
    'meetings',  # Need Classroom model for head count feature
    'camera_api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

# CORS settings - allow main app to access camera service
CORS_ALLOWED_ORIGINS = [
    "https://localhost",
    "https://localhost:8443",
    "https://127.0.0.1",
    "https://127.0.0.1:8443",
    "https://10.17.2.47",
    "https://10.17.2.47:8443",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://10.17.2.47:8000",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True  # Allow all origins for development

ROOT_URLCONF = 'camera_service.urls'

# Use the same database as main project
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': MAIN_PROJECT_DIR / 'db.sqlite3',
    }
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
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
        'camera_api': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
