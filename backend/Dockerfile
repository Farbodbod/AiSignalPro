FROM python:3.11-slim-bullseye

# نصب پیش‌نیازهای ساخت
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
    && rm -rf /var/lib/apt/lists/*

# دانلود و نصب کتابخانه‌ی اصلی TA-Lib (نسخه C)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzvf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# ادامه نصب پایتون و پروژه
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
