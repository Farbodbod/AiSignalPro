# استفاده از تصویر پایه سبک پایتون
FROM python:3.11-slim

# نصب پیش‌نیازهای سیستمی
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
    libxml2-dev \
    libxslt-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# دانلود و نصب TA-Lib نسخه 0.4.0 از سورس
RUN cd /tmp && \
    curl -L http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz -o ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install

# اضافه کردن مسیر کتابخانه TA-Lib
ENV LD_LIBRARY_PATH="/usr/lib:$LD_LIBRARY_PATH"

# نصب پکیج‌های پایتون
RUN pip install --no-cache-dir \
    ta-lib==0.6.4 \
    pandas \
    numpy

# دستور پیش‌فرض
CMD [ "python3" ]
