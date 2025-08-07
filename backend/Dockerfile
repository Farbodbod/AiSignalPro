# استفاده از نسخه پایدار Python 3.10
FROM python:3.10-slim-bullseye

# نصب ابزارهای موردنیاز برای کامپایل TA-Lib و سایر پکیج‌ها
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

# دانلود و نصب نسخه C از TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# اضافه کردن مسیر shared libs برای TA-Lib
ENV LD_LIBRARY_PATH=/usr/lib

# تنظیم دایرکتوری کاری پروژه
WORKDIR /app

# کپی فایل نیازمندی‌ها
COPY requirements.txt .

# نصب پکیج‌های پایتون
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه
COPY . .

# باز کردن پورت 8000 برای uvicorn
EXPOSE 8000

# اجرای پروژه با uvicorn
CMD ["uvicorn", "core.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
