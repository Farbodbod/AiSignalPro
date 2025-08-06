# Dockerfile (نسخه نهایی و ساده‌شده بدون TA-Lib)

# ۱. انتخاب سیستم‌عامل پایه (نسخه slim دوباره کافی است)
FROM python:3.11-slim-bullseye

# ۲. تنظیم پوشه کاری
WORKDIR /app

# ۳. کپی کردن فایل نیازمندی‌ها و نصب پکیج‌های پایتون
# دیگر نیازی به نصب ابزارهای کامپایل و غیره نیست
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ۴. کپی کردن تمام کدهای پروژه
COPY . .

# ۵. تعریف دستور نهایی برای اجرای برنامه
CMD ["gunicorn", "trading_app.wsgi"]
