# Dockerfile نهایی برای Railway با پشتیبانی از TA-Lib

FROM python:3.11-slim-bullseye

# نصب پیش‌نیازهای سیستمی برای کامپایل TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    curl \
    git \
    libtool \
    automake \
    autoconf \
    libffi-dev \
    libssl-dev \
    libta-lib0 \
    libta-lib0-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
