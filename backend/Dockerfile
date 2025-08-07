FROM python:3.10-slim

# نصب ابزارها و وابستگی‌ها
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
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# نصب نسخه‌ی C از TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    ldconfig && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# ست کردن PATH برای اطمینان
ENV LD_LIBRARY_PATH="/usr/lib:/usr/local/lib"
ENV CPATH="/usr/include"

# کپی فایل‌ها و نصب
WORKDIR /app
COPY . /app

RUN pip install --upgrade pip

# نصب TA-Lib (نسخه پایتونی) بعد از اطمینان از نصب libta_lib.so
RUN pip install --no-cache-dir TA-Lib==0.6.4

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
