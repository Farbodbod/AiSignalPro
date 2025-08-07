# Dockerfile (نسخه نهایی و تمیز برای Procfile)

# ۱. انتخاب سیستم‌عامل پایه
FROM python:3.11-slim-bullseye

# ۲. تنظیم پوشه کاری
WORKDIR /app

# ۳. کپی کردن فایل نیازمندی‌ها و نصب پکیج‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ۴. کپی کردن تمام کدهای پروژه
COPY . .

# دستور CMD حذف شد، زیرا Procfile اکنون مسئولیت اجرای فرآیندها را بر عهده دارد.
