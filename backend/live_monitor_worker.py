# live_monitor_worker.py

import time
import logging
import pandas as pd
from typing import Dict, Any

# برای اینکه این اسکریپت بتواند جنگو و مدل‌های ما را بشناسد
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

# حالا می‌توانیم موتورهای خود را وارد کنیم
from core.views import _generate_signal_object
from engines.telegram_handler import TelegramHandler

# تنظیمات
SYMBOLS_TO_MONITOR = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
POLL_INTERVAL_SECONDS = 300 # هر ۵ دقیقه یک بار

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def monitor_loop():
    """حلقه اصلی که به طور مداوم بازار را رصد می‌کند."""
    try:
        telegram = TelegramHandler()
        logging.info("Live Monitoring Worker started successfully.")
        telegram.send_message("*✅ ربات مانیتورینگ با موفقیت فعال شد.*")
    except ValueError as e:
        logging.error(e)
        return # اگر کلیدهای تلگرام نبود، سرویس متوقف می‌شود

    while True:
        logging.info("Starting new monitoring cycle...")
        for symbol in SYMBOLS_TO_MONITOR:
            try:
                logging.info(f"Analyzing {symbol}...")
                # از تابع قدرتمندی که در views ساختیم، دوباره استفاده می‌کنیم
                signal_obj = _generate_signal_object(symbol, None, 'balanced')

                if signal_obj and signal_obj.get("signal_type") != "HOLD":
                    # اگر سیگنال مهمی (BUY/SELL) وجود داشت، آن را به تلگرام ارسال کن
                    signal_type = signal_obj.get("signal_type")
                    price = signal_obj.get("current_price")
                    confidence = signal_obj.get("confidence")

                    message = (
                        f"🚨 *سیگنال جدید: {symbol}*\n\n"
                        f"*{signal_type}* @ `${price}`\n"
                        f"اعتماد هوش مصنوعی: *{confidence}%*\n"
                        f"منبع داده: `{signal_obj.get('scores', {}).get('details', {}).get('1h', {}).get('source')}`"
                    )
                    telegram.send_message(message)
                    logging.info(f"Alert sent for {symbol}: {signal_type}")
                    # کمی تأخیر برای جلوگیری از بلاک شدن توسط تلگرام
                    time.sleep(5)

            except Exception as e:
                logging.error(f"Error processing symbol {symbol}: {e}")

        logging.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds.")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    monitor_loop()

