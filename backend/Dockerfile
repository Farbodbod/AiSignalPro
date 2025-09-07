# ۱. انتخاب سیستم‌عامل پایه
FROM python:3.10-slim

# تنظیم متغیرهای محیطی
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ۲. نصب ابزارهای سیستمی ضروری (اضافه شد: git, wget, curl)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        pkg-config \
        libssl-dev \
        libffi-dev \
        git \
        wget \
        curl && \
    rm -rf /var/lib/apt/lists/*

# ۳. تنظیم دایرکتوری کاری
WORKDIR /app

# ۴. کپی کردن فایل requirements.txt و نصب وابستگی‌های پایتون
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# ۵. کپی کردن تمام کدهای پروژه
COPY . .

# ۶. دسترسی اجرا به اسکریپت
RUN chmod +x /app/start_worker.sh

# ۷. پورت مورد نظر
EXPOSE 8000

# نکته کلیدی: خط CMD حذف شده است. دستور شروع در Railway تعریف می‌شود.
