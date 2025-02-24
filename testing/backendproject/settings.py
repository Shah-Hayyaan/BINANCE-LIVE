from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Secret Key
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-+f&skilipn2a$7$u0&7-6-^4orl_s($%!&(m69twej4awidh=$')

# Debug mode (Set to False in production)
DEBUG = True

# Allowed Hosts
ALLOWED_HOSTS = ['localhost','binance-live.onrender.com','*','127.0.0.1','binance-stream.onrender.com']

# Application definition
INSTALLED_APPS = [
    'daphne',  # ASGI server
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'backendapp',  # Your main app
    'channels',  # WebSockets
    'corsheaders',  # CORS support
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Keep at the top
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# URLs & WSGI/ASGI setup
ROOT_URLCONF = 'backendproject.urls'
WSGI_APPLICATION = 'backendproject.wsgi.application'
ASGI_APPLICATION = 'backendproject.asgi.application'

# Database configuration (modify as needed)
DATABASES = {
    'default': dj_database_url.config(default='sqlite:///db.sqlite3')
}

# Channel Layers (Redis for WebSockets)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL","redis://red-cuu4tlnnoe9s73d29pl0:6379")],  # Ensure Redis is running
        },
    },
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://binance-stream.onrender.com',
    'https://binance-live.onrender.com',
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:[0-9]+$",
    r"^https://binance-live\.onrender\.com$",
    r"^https://binance-stream\.onrender\.com$",
]

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

# Static and Media Files
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
