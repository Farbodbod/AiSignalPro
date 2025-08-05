# Dockerfile (نسخه نهایی و قطعی برای AiSignalPro)

# ۱. انتخاب سیستم‌عامل پایه (یک لینوکس دبیان بهینه با پایتون ۳.۱۱)
FROM python:3.11-slim-buster

# ۲. نصب پیش‌نیازهای سیستمی با apt-get
# این بار ما کنترل کامل روی سیستم‌عامل داریم
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    tar \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ۳. دانلود، کامپایل و نصب کتابخانه C از سورس کد اصلی آن
# این دستورات در یک محیط باثبات و قابل پیش‌بینی اجرا می‌شوند
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# ۴. تنظیم پوشه کاری داخل کانتینر
WORKDIR /app

# ۵. کپی کردن فایل نیازمندی‌ها و نصب پکیج‌های پایتون
# این مرحله پس از نصب موفقیت‌آمیز کتابخانه C اجرا می‌شود
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ۶. کپی کردن تمام کدهای پروژه به داخل کانتینر
COPY . .

# ۷. تعریف دستور نهایی برای اجرای برنامه
# مطمئن شوید gunicorn در requirements.txt شما هست
# این دستور سرور جنگو شما را اجرا می‌کند
CMD ["gunicorn", "trading_app.wsgi"]

