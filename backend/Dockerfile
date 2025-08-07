# استفاده از ایمیج سبک پایتون
FROM python:3.11-slim-bullseye

# نصب ابزارهای مورد نیاز برای کامپایل TA-Lib
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
    && rm -rf /var/lib/apt/lists/*

# دانلود و کامپایل نسخه‌ی C از TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# اضافه کردن کتابخانه به متغیرهای محیطی برای linker
ENV LD_LIBRARY_PATH="/usr/lib:$LD_LIBRARY_PATH"

# تنظیم مسیر کاری پروژه
WORKDIR /app

# کپی فایل نیازمندی‌ها
COPY requirements.txt .

# نصب پکیج‌های پایتون
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه به داخل کانتینر
COPY . .

# اجرای اپلیکیشن (در صورت نیاز)
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
