# Dockerfile (آخرین تلاش با ایمیج کامل و بازرسی)

# ۱. ✨✨ تغییر کلیدی: استفاده از ایمیج کامل به جای نسخه slim ✨✨
FROM python:3.11-bullseye

# ۲. نصب پیش‌نیازهای سیستمی
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    tar \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ۳. دانلود، کامپایل و نصب کتابخانه C
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# ۴. ✨✨ مرحله جدید: بازرسی و تایید نصب ✨✨
# ما محتویات پوشه‌های نصب را در لاگ چاپ می‌کنیم تا مطمئن شویم فایل‌ها آنجا هستند.
RUN ls -l /usr/include/ta-lib/ && ls -l /usr/lib/libta_*

# ۵. تعریف متغیرهای محیطی برای آدرس‌دهی مستقیم
ENV TA_INCLUDE_PATH=/usr/include
ENV TA_LIBRARY_PATH=/usr/lib

# ۶. تنظیم پوشه کاری
WORKDIR /app

# ۷. کپی و نصب نیازمندی‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ۸. کپی کردن کدهای پروژه
COPY . .

# ۹. تعریف دستور نهایی برای اجرای برنامه
CMD ["gunicorn", "trading_app.wsgi"]
