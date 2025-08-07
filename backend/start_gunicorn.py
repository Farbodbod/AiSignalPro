# --- start_gunicorn.py ---

import os
import sys
import subprocess

print("--- Starting Gunicorn Launcher Script ---")

# خواندن پورت از متغیر محیطی Railway، با یک مقدار پیش‌فرض برای تست محلی
port = os.environ.get('PORT', '8000')
# خواندن تعداد ورکرها از متغیر محیطی (بسیاری از پلتفرم‌ها این را تنظیم می‌کنند)
workers = os.environ.get('WEB_CONCURRENCY', 3)

print(f"PORT detected: {port}")
print(f"Number of workers: {workers}")

# ساخت دستور کامل و صحیح Gunicorn
command = [
    'gunicorn',
    'trading_app.wsgi',
    '--bind',
    f'0.0.0.0:{port}',
    '--workers',
    str(workers)
]

print(f"Executing command: {' '.join(command)}")

# اجرای Gunicorn
# این دستور فرآیند پایتون فعلی را با Gunicorn جایگزین می‌کند
try:
    subprocess.run(command, check=True)
except FileNotFoundError:
    print("Error: 'gunicorn' command not found. Make sure it's installed in your requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred while trying to start Gunicorn: {e}")
    sys.exit(1)
