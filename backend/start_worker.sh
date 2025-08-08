#!/bin/sh

# این اسکریپت تضمین می‌کند که دیتابیس قبل از شروع به کار ورکر، آماده است.

echo "--- [Worker] Running Django migrations before starting... ---"
python manage.py migrate --no-input

echo "--- [Worker] Migrations complete. Starting Live Monitor Worker... ---"
# دستور exec فرآیند فعلی را با فرآیند پایتون جایگزین می‌کند که بهینه‌تر است
exec python -u live_monitor_worker.py
