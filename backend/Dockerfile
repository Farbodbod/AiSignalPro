# Dockerfile (نسخه نهایی و قطعی با متغیر زمان اجرا)

# ۱. انتخاب سیستم‌عامل پایه
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

# ۴. بازرسی و تایید نصب (این خط می‌تواند بماند یا حذف شود)
RUN ls -l /usr/include/ta-lib/ && ls -l /usr/lib/libta_*

# ۵. تعریف متغیرهای محیطی برای بیلد
ENV TA_INCLUDE_PATH=/usr/include
ENV TA_LIBRARY_PATH=/usr/lib

# ۶. ✨✨ اصلاحیه کلیدی و نهایی: تعریف متغیر محیطی برای زمان اجرا ✨✨
ENV LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

# ۷. تنظیم پوشه کاری
WORKDIR /app

# ۸. کپی و نصب نیازمندی‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ۹. کپی کردن کدهای پروژه
COPY . .

# ۱۰. تعریف دستور نهایی برای اجرای برنامه
CMD ["gunicorn", "trading_app.wsgi"]

