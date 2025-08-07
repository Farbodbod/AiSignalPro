# ۱. انتخاب سیستم‌عامل پایه
# استفاده از یک ایمیج پایه پایتون 3.11 سبک و مدرن.
# 'slim-bookworm' بر اساس دبیان 12 است که برای پایتون 3.11 مناسب است.
FROM python:3.11-slim-bookworm

# تنظیم متغیرهای محیطی برای عملیات apt-get غیرتعاملی و خروجی بافر نشده پایتون
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ۲. نصب ابزارهای سیستمی ضروری (فقط برای سایر وابستگی‌ها، نه TA-Lib)
#    'build-essential' و 'python3-dev' ممکن است برای سایر پکیج‌های C-extension در requirements.txt لازم باشند.
#    'rm -rf /var/lib/apt/lists/*' لیست های بسته apt را پاک می کند تا حجم ایمیج را بیشتر کاهش دهد.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        pkg-config \
        libssl-dev \
        libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# ۳. تنظیم دایرکتوری کاری برای برنامه شما در داخل کانتینر.
WORKDIR /app

# ۴. کپی کردن فایل requirements.txt و نصب وابستگی های پایتون.
#    TA-Lib اکنون به عنوان یک پکیج از پیش کامپایل شده نصب خواهد شد.
COPY requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt

# ۵. کپی کردن بقیه کد برنامه شما به داخل کانتینر.
COPY..

# ۶. پورت مورد نظر برنامه شما را آشکار می کند (اگر یک برنامه وب است).
EXPOSE 8000
