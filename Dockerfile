# syntax=docker/dockerfile:1

# ---- Base Python ----
FROM python:3.11-slim AS base

# تنظیمات محیطی پایتون
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# نصب پکیج‌های سیستمی لازم
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

# نصب پکیج‌های پایتون
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# کپی کل پروژه
COPY . .

# پورت Railway
ENV PORT=8000
EXPOSE 8000

# دستور شروع کانتینر
CMD python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    gunicorn trading_app.wsgi:application --bind 0.0.0.0:$PORT
