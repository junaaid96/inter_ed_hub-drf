"""
Django settings for InterEd Hub.

Everything environment-specific is read from environment variables (or a
local `.env` file). `neon deploy` / `neon env pull` write DATABASE_URL and the
AWS_* object-storage variables for the linked Neon branch automatically.
"""

from pathlib import Path

import dj_database_url
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
for candidate in ('.env', '.env.local'):
    if (BASE_DIR / candidate).exists():
        environ.Env.read_env(BASE_DIR / candidate)

DEBUG = env.bool('DEBUG', default=False)
SECRET_KEY = env('SECRET_KEY', default='insecure-dev-key-change-me' if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError('SECRET_KEY must be set when DEBUG is off.')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000').rstrip('/')
BACKEND_URL = env('BACKEND_URL', default='http://localhost:8000').rstrip('/')

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[FRONTEND_URL])
CORS_ALLOWED_ORIGIN_REGEXES = env.list('CORS_ALLOWED_ORIGIN_REGEXES', default=[])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[BACKEND_URL, FRONTEND_URL])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'uploads',
    'department',
    'students',
    'teachers',
    'accounts',
    'courses',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'inter_ed_hub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'inter_ed_hub.wsgi.application'


# Database: Neon Postgres via DATABASE_URL, SQLite for quick local hacking.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'local.sqlite3'}",
        conn_max_age=env.int('DB_CONN_MAX_AGE', default=60),
        conn_health_checks=True,
    )
}


# Object storage: Neon Object Storage (S3 compatible). When the AWS_* variables
# are missing, uploads fall back to the local filesystem so the app still runs
# offline; never use that fallback in production.
STORAGE_BUCKET = env('STORAGE_BUCKET', default='intered-hub-uploads')
AWS_ENDPOINT_URL_S3 = env('AWS_ENDPOINT_URL_S3', default='')
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
AWS_REGION = env('AWS_REGION', default='us-east-2')
STORAGE_BACKEND = env(
    'STORAGE_BACKEND',
    default='s3' if AWS_ENDPOINT_URL_S3 and AWS_ACCESS_KEY_ID else 'local',
)
LOCAL_STORAGE_ROOT = Path(env('LOCAL_STORAGE_ROOT', default=str(BASE_DIR / 'local_storage')))
# Seconds a presigned video URL stays valid; the player refreshes it on expiry.
VIDEO_URL_TTL = env.int('VIDEO_URL_TTL', default=4 * 60 * 60)
MAX_VIDEO_BYTES = env.int('MAX_VIDEO_BYTES', default=5 * 1024 ** 3)
MAX_IMAGE_BYTES = env.int('MAX_IMAGE_BYTES', default=10 * 1024 ** 2)
MULTIPART_THRESHOLD = env.int('MULTIPART_THRESHOLD', default=64 * 1024 ** 2)
MULTIPART_PART_SIZE = env.int('MULTIPART_PART_SIZE', default=16 * 1024 ** 2)
# Apply the bucket CORS rules on the first upload of each process, so browser
# uploads work even if `configure_bucket_cors` was never run during deploys.
STORAGE_AUTO_CORS = env.bool('STORAGE_AUTO_CORS', default=True)


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_PAGINATION_CLASS': 'courses.pagination.StandardPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': env('ANON_THROTTLE', default='120/min'),
        'user': env('USER_THROTTLE', default='600/min'),
        'auth': env('AUTH_THROTTLE', default='10/min'),
    },
}


# Email: when EMAIL_HOST is set, new accounts must confirm their address.
EMAIL_HOST = env('EMAIL_HOST', default='')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_USE_TLS = True
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
REQUIRE_EMAIL_ACTIVATION = env.bool('REQUIRE_EMAIL_ACTIVATION', default=bool(EMAIL_HOST))


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
# Serve app static files (Django admin, DRF) straight from the installed apps,
# so the API works even when the host never runs collectstatic.
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
