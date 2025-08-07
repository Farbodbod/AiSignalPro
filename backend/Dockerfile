# پایه: python رسمی
FROM python:3.10-slim

# نصب ابزارهای ضروری
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    curl \
    gcc \
    make \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    liblzma-dev \
    libgdbm-dev \
    libnss3-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# نصب سورس C مربوط به TA-Lib (نسخه 0.4.0)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# تنظیم مسیرهای مربوط به TA-Lib
ENV LD_LIBRARY_PATH="/usr/lib:$LD_LIBRARY_PATH"
ENV CPATH="/usr/include:$CPATH"

# کپی فایل‌های پروژه
WORKDIR /app
COPY . /app

# نصب وابستگی‌های پایتون
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# اجرای اپلیکیشن
CMD ["python", "main.py"]
