# syntax=docker/dockerfile:1

# ---- Base Python ----
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# سیستمی که برای بعضی پکیج‌ها لازمه (build-essential و curl برای مطمئن شدن)
# اگر build زمان‌بر شد می‌تونیم کمش کنیم
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

# کپی فایل‌های requirements و نصب
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# کپی کل پروژه
COPY . .

# پورت Railway
ENV PORT=8000

# جمع کردن استاتیک و مایگریشن در زمان استارت (نه بیلد) تا env آماده باشه
CMD sh -c \"python manage.py migrate --noinput && \\\n           python manage.py collectstatic --noinput && \\\n           gunicorn trading_app.wsgi:application --bind 0.0.0.0:\${PORT}\"
