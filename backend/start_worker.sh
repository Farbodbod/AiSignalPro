#!/bin/sh

# مرحله ۱: منتظر می‌مانیم تا دیتابیس کاملاً آماده شود.
echo "--- [Worker] Waiting for database to be ready... ---"
python manage.py wait_for_db

# مرحله ۲: پس از آماده شدن دیتابیس، برنامه اصلی را اجرا می‌کنیم.
echo "--- [Worker] Database is ready. Starting Live Monitor Worker... ---"
exec python -u live_monitor_worker.py
