from pathlib import Path
import os # این را اضافه می‌کنیم

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-gg$_ng&y__6+j%@-x02b5mm9%r%ga0x+#45m!6y26jktohk04(')

# SECURITY WARNING: don't run with debug turned on in production!
# در محیط Railway، این به صورت خودکار False می‌شود.
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# === هاست‌های مجاز ===
ALLOWED_HOSTS = [
    'aisignalpro-production.up.railway.app',
    '.vercel.app', # به Vercel اجازه اتصال می‌دهد
    'localhost',
    '127.0.0.1',
]

# === اپلیکیشن‌های نصب شده ===
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic', # برای فایل‌های استاتیک
    'django.contrib.staticfiles',
    'corsheaders', # اپلیکیشن CORS
    'core',
    'corsheaders',
]


# === میان‌افزارها (Middleware) ===
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # میان‌افزار WhiteNoise
    'corsheaders.middleware.CorsMiddleware', # میان‌افزار CORS
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trading_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'trading_app.wsgi.application'

# === پایگاه داده (Database) ===
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ... (بقیه تنظیمات اعتبارسنجی رمز عبور و زبان) ...
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# === فایل‌های استاتیک (Static files) ===
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === تنظیمات CORS ===
CORS_ALLOWED_ORIGINS = [
    "https://ai-signal-pro.vercel.app",
]
CSRF_TRUSTED_ORIGINS = ["https://ai-signal-pro.vercel.app"]

