FROM python:3.10-slim

# نصب ابزارهای مورد نیاز
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
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
    libgdbm-dev \
    libnss3-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# نصب TA-Lib C library (نسخه 0.4.0)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr/local && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# لینک کردن دستی اگر فایل .so در /usr/local/lib نبود
RUN ldconfig && \
    if [ ! -f /usr/lib/libta_lib.so ]; then ln -s /usr/local/lib/libta_lib.so /usr/lib/libta_lib.so || true; fi

# تنظیم مسیرها برای linker
ENV LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"
ENV LIBRARY_PATH="/usr/local/lib:$LIBRARY_PATH"
ENV CPATH="/usr/local/include:$CPATH"

# کپی پروژه
WORKDIR /app
COPY . /app

# نصب پکیج‌ها
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
