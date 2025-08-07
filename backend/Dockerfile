# ۱. انتخاب سیستم‌عامل پایه
FROM python:3.11-slim-bookworm

# تنظیم متغیرهای محیطی
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ۲. نصب ابزارهای سیستمی ضروری
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        pkg-config \
        libssl-dev \
        libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# ۳. تنظیم دایرکتوری کاری
WORKDIR /app

# ۴. کپی کردن فایل requirements.txt و نصب وابستگی های پایتون
# ✨ اصلاحیه: فاصله بین نام فایل و نقطه اضافه شد
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ۵. کپی کردن تمام کدهای پروژه
COPY . .

# ۶. پورت مورد نظر را آشکار می‌کند (برای سرویس وب)
EXPOSE 8000

# نکته کلیدی: خط CMD حذف شده است. دستور شروع در خود Railway تعریف می‌شود.
