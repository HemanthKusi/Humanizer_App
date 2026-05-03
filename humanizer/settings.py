"""
settings.py
-----------
Django's main configuration file.
Every Django project has exactly one settings.py.
It controls the database, installed apps, templates, security, and more.
"""

# SSL certificate configuration
import ssl
import certifi
import os
os.environ['SSL_CERT_FILE'] = certifi.where()

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
    'django.contrib.sites',      # Required by allauth — manages site domain info

    # Allauth apps
    'allauth',                          # Core allauth
    'allauth.account',                  # Email/password auth (allauth's version)
    'allauth.socialaccount',            # Social auth base
    'allauth.socialaccount.providers.google',  # Google provider

    'django.contrib.humanize',       # Template filters: intcomma, timesince, etc.
    'core',                      # Our main app
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
    'allauth.account.middleware.AccountMiddleware',
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

# ─── LOGGING ─────────────────────────────────────────────────────────
#
# Three log files:
#   app.log      — general application events (info+)
#   api.log      — every API request with timing (info+)
#   security.log — rate limits, profanity, suspicious activity (warning+)
#
# Log rotation: each file maxes at 5MB, keeps 3 backups.
# So max disk usage = 3 files × 5MB × 3 backups = 45MB total.

import os

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    # ── Formatters: how log lines look ──
    'formatters': {
        'standard': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'detailed': {
            'format': '[{asctime}] {levelname} {name} ({filename}:{lineno}): {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },

    # ── Handlers: where logs go ──
    'handlers': {
        # Console — always active, useful during development
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'INFO',
        },

        # app.log — general application events
        'app_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'app.log'),
            'maxBytes': 5 * 1024 * 1024,    # 5MB per file
            'backupCount': 3,                 # Keep 3 old files
            'formatter': 'detailed',
            'level': 'INFO',
        },

        # api.log — API request tracking
        'api_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'api.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'detailed',
            'level': 'INFO',
        },

        # security.log — rate limits, profanity, attacks
        'security_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'security.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'detailed',
            'level': 'WARNING',
        },
    },

    # ── Loggers: named channels ──
    'loggers': {
        # General app logger
        'app': {
            'handlers': ['console', 'app_file'],
            'level': 'INFO',
            'propagate': False,
        },

        # API request logger
        'api': {
            'handlers': ['console', 'api_file'],
            'level': 'INFO',
            'propagate': False,
        },

        # Security logger
        'security': {
            'handlers': ['console', 'security_file'],
            'level': 'WARNING',
            'propagate': False,
        },

        # Django's own logging
        'django': {
            'handlers': ['console', 'app_file'],
            'level': 'WARNING',
            'propagate': False,
        },

        # Catch database query errors
        'django.db.backends': {
            'handlers': ['console', 'app_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ─── AUTHENTICATION ──────────────────────────────────────────────────────────
#
# Django's auth system + django-allauth for Google Sign-In.
#
# How it works:
# 1. User clicks "Sign in with Google" on our login page
# 2. They get redirected to Google's OAuth consent screen
# 3. Google redirects back to our callback URL with a token
# 4. allauth verifies the token, creates/links the user account
# 5. User is logged in and redirected to the homepage

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Required by django.contrib.sites — allauth uses this
# to know which domain it's running on
SITE_ID = 1

# Custom account adapter for allauth
# This tells allauth to use our adapter which redirects to our custom login/signup pages.
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ── Allauth settings ──

# Use our custom login/signup pages, not allauth's built-in ones
ACCOUNT_LOGIN_URL = '/login/'
ACCOUNT_SIGNUP_URL = '/signup/'

# Redirect allauth's default login/signup URLs to ours
ACCOUNT_ADAPTER = 'core.adapters.CustomAccountAdapter'

# After social login, redirect to homepage
SOCIALACCOUNT_LOGIN_ON_GET = True

# Don't ask for extra info after Google sign-in
# Just create the account and log them in
SOCIALACCOUNT_AUTO_SIGNUP = True

# Use email as the primary identifier
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'

# Don't send email verification (we can add this later)
ACCOUNT_EMAIL_VERIFICATION = 'none'

# Google provider settings — reads from .env
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
    },
}

# ─── EMAIL ───────────────────────────────────────────────────────────
#
# Uses Gmail SMTP to send verification codes and password reset emails.
# Free for up to 500 emails/day.
#
# Requires a Gmail App Password (not your regular password).
# The app password is stored in .env for security.
#
# In development with DEBUG=True, if no email credentials are set,
# emails print to the console instead of actually sending.

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Fallback: if no email credentials, print emails to console (dev only)
if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'