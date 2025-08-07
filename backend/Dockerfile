# پایه: Python سبک با قابلیت کامپایل
FROM python:3.11-slim-bullseye

# نصب ابزارهای لازم برای کامپایل TA-Lib و پکیج‌های ML
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
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# نصب TA-Lib (C Library)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# اضافه کردن مسیر shared libs
ENV LD_LIBRARY_PATH=/usr/lib

# مسیر کاری پروژه
WORKDIR /app

# کپی فایل نیازمندی‌ها
COPY requirements.txt .

# آپدیت pip و نصب پکیج‌های پایتون
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه به داخل کانتینر
COPY . .

# پورت مورد استفاده (اختیاری)
EXPOSE 8000

# دستور اجرای نهایی (اگر از Uvicorn استفاده می‌کنی برای API یا ASGI)
CMD ["uvicorn", "project_name.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
