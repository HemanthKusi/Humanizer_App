"""
settings.py
-----------
Django's main configuration file.
Every Django project has exactly one settings.py.
It controls the database, installed apps, templates, security, and more.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from our .env file
# This must happen before we try to read any env variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR is the root of our project (the humanizer-app folder)
BASE_DIR = Path(__file__).resolve().parent.parent


# ─── SECURITY ────────────────────────────────────────────────────────────────

# Secret key is used for cryptographic signing in Django.
# We read it from .env so it is never hardcoded in code.
# os.environ.get() reads a value from environment variables.
# The second argument is a fallback (only used in development if .env is missing)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'fallback-dev-key-change-in-production')

# Debug mode shows detailed error pages.
# Must be False in production. We read it from .env.
# The string 'True' in .env becomes the boolean True here.
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Which hostnames are allowed to serve this app.
# In development, localhost is fine.
# In production, you add your real domain here.
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# ─── INSTALLED APPS ──────────────────────────────────────────────────────────

# These are all the Django apps that are active in this project.
# Django's built-in apps come first, then ours.
INSTALLED_APPS = [
    'django.contrib.admin',      # Django admin panel
    'django.contrib.auth',       # User authentication
    'django.contrib.contenttypes',
    'django.contrib.sessions',   # Session management
    'django.contrib.messages',   # Flash messages
    'django.contrib.staticfiles',# CSS, JS, images
    'core',                      # Our main app (we just created this)
]

# ─── SECURITY HEADERS ───────────────────────────────────────────
# These tell browsers to enforce security policies

# Only send HTTPS in production
SECURE_SSL_REDIRECT = not DEBUG

# Prevent clickjacking — no one can embed your site in an iframe
X_FRAME_OPTIONS = 'DENY'

# Prevent MIME type sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True

# Enable browser XSS filter
SECURE_BROWSER_XSS_FILTER = True

# HSTS — tell browsers to always use HTTPS (production only)
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000        # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Cookie security
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True


# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────

# Middleware are functions that run on every request and response.
# Think of them as a pipeline that every request passes through.
MIDDLEWARE = [
    'core.middleware.SimpleRateLimiter',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # CSRF protection (important for forms)
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CSRF settings
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_HTTPONLY = False    # JS needs to read it

# Limit request body size to 100KB (more than enough for 500 words)
DATA_UPLOAD_MAX_MEMORY_SIZE = 102400  # 100KB in bytes

# The root URL configuration file.
# Django starts here when routing requests.
ROOT_URLCONF = 'humanizer.urls'


# ─── TEMPLATES ────────────────────────────────────────────────────────────────

# This tells Django where to find our HTML template files.
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # DIRS is a list of folders to search for templates
        # We use BASE_DIR so the path works on any machine
        'DIRS': [BASE_DIR / 'templates'],
        # APP_DIRS: True means Django also looks inside each app's templates folder
        # This is how it finds core/templates/core/index.html
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'humanizer.wsgi.application'


# ─── DATABASE ─────────────────────────────────────────────────────────────────

# SQLite is a simple file-based database.
# Perfect for development. No setup required.
# The database is stored as a single file: db.sqlite3
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ─── PASSWORD VALIDATION ─────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─── INTERNATIONALIZATION ────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ─── STATIC FILES ────────────────────────────────────────────────────────────

# Leading slash is required in Django 6.0
STATIC_URL = '/static/'

# Explicitly tell Django which finders to use.
# AppDirectoriesFinder looks inside each app's static/ folder.
# This is how it finds core/static/core/style.css
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
]

# Default primary key type for database models
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'