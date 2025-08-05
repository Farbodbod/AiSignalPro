# Dockerfile (نسخه نهایی با آدرس‌دهی مستقیم)

# ۱. انتخاب سیستم‌عامل پایه
FROM python:3.11-slim-bullseye

# ۲. نصب پیش‌نیازهای سیستمی
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    tar \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ۳. دانلود، کامپایل و نصب کتابخانه C در مسیر استاندارد /usr
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# ۴. ✨✨ اصلاحیه کلیدی: تعریف متغیرهای محیطی ✨✨
# ما به صورت صریح به pip می‌گوییم که فایل‌های هدر (.h) و کتابخانه (.so) کجا هستند.
ENV TA_INCLUDE_PATH=/usr/include
ENV TA_LIBRARY_PATH=/usr/lib

# ۵. تنظیم پوشه کاری داخل کانتینر
WORKDIR /app

# ۶. کپی کردن فایل نیازمندی‌ها و نصب پکیج‌های پایتون
# این بار pip آدرس دقیق را می‌داند و نباید شکست بخورد.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ۷. کپی کردن تمام کدهای پروژه به داخل کانتینر
COPY . .

# ۸. تعریف دستور نهایی برای اجرای برنامه
CMD ["gunicorn", "trading_app.wsgi"]
