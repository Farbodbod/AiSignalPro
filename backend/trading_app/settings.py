import os
from pathlib import Path
import dj_database_url # <--- برای اتصال به دیتابیس ریلوی

# مسیر پایه پروژه
BASE_DIR = Path(__file__).resolve().parent.parent

# ===========================
# SECURITY
# ===========================
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key-placeholder')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

# --- تغییر: لیست میزبان‌های مجاز برای امنیت بیشتر ---
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')


# ===========================
# INSTALLED APPS
# ===========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # برنامه‌های Third-party
    'corsheaders',

    # برنامه‌های پروژه
    'core',
    # --- تغییر: engines یک اپ جنگو نیست و نباید اینجا باشد ---
]

# ===========================
# MIDDLEWARE
# ===========================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # باید در بالای لیست باشد
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # برای سرویس‌دهی فایل‌های استاتیک
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trading_app.urls'
WSGI_APPLICATION = 'trading_app.wsgi.application'

# ===========================
# TEMPLATES
# ===========================
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

# ===========================
# DATABASE
# ===========================
# --- تغییر: اتصال هوشمند به دیتابیس PostgreSQL ریلوی ---
if 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
    }
else:
    # در صورت نبودن متغیر، از SQLite برای تست محلی استفاده می‌شود
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ===========================
# PASSWORD VALIDATION
# ===========================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ===========================
# INTERNATIONALIZATION
# ===========================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ===========================
# STATIC FILES (پیکربندی شده برای Whitenoise)
# ===========================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ===========================
# DEFAULT PRIMARY KEY FIELD
# ===========================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ===========================
# CORS SETTINGS (پیکربندی امن)
# ===========================
CORS_ALLOWED_ORIGINS = [
    "https://ai-signal-pro-glt-main-ai-signal-pro.vercel.app",
    "https://ai-signal-ajqvbf8jg-ai-signal-pro.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

# --- تغییر: افزودن دامنه‌های ورسل به CSRF_TRUSTED_ORIGINS ---
CSRF_TRUSTED_ORIGINS = [
    "https://*.vercel.app",
    "https://*.up.railway.app",
]
