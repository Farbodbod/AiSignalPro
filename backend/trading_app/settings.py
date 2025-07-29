# trading_app/settings.py (نسخه نهایی با تنظیمات صحیح CORS)

import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key-placeholder')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') != 'True'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # --- Middleware مربوط به CORS باید همیشه در بالای لیست باشد ---
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trading_app.urls'
WSGI_APPLICATION = 'trading_app.wsgi.application'
ASGI_APPLICATION = 'trading_app.asgi.application'

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

if 'DATABASE_URL' in os.environ:
    DATABASES = {'default': dj_database_url.config(conn_max_age=600, ssl_require=True)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

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

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- ✨ تنظیمات نهایی و صحیح CORS برای اتصال Vercel به Railway ✨ ---
CORS_ALLOWED_ORIGINS = [
    # آدرس اصلی داشبورد شما
    "https://ai-signal-pro.vercel.app",
    # برای تست در محیط لوکال
    "http://localhost:3000",
]

# (اختیاری اما بسیار پیشنهادی) این به تمام پیش‌نمایش‌های Vercel نیز اجازه دسترسی می‌دهد
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://ai-signal-pro-.*\.vercel\.app$",
]

CSRF_TRUSTED_ORIGINS = [
    "https://*.railway.app",
    "https://*.vercel.app",
]
