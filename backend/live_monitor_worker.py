# live_monitor_worker.py - نسخه نهایی و کامل

import time
import logging
from typing import Dict, Any

# برای اینکه این اسکریپت بتواند جنگو و مدل‌های ما را بشناسد
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.views import _generate_signal_object
from engines.telegram_handler import TelegramHandler

# تنظیمات
SYMBOLS_TO_MONITOR = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
POLL_INTERVAL_SECONDS = 300 # هر ۵ دقیقه یک بار
SIGNAL_CACHE_TTL_SECONDS = 1800 # سیگنال مشابه تا ۳۰ دقیقه ارسال نشود

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SignalCache:
    """یک حافظه موقت برای جلوگیری از ارسال سیگنال‌های تکراری."""
    def __init__(self, ttl_seconds: int):
        self.cache = {}
        self.ttl = ttl_seconds

    def is_duplicate(self, symbol: str, signal_type: str) -> bool:
        """بررسی می‌کند که آیا سیگنال جدید تکراری است یا خیر."""
        now = time.time()
        if symbol in self.cache:
            last_signal, last_time = self.cache[symbol]
            if signal_type == last_signal and (now - last_time) < self.ttl:
                return True
        return False

    def store(self, symbol: str, signal_type: str):
        """سیگنال جدید را در حافظه ذخیره می‌کند."""
        self.cache[symbol] = (signal_type, time.time())

def get_primary_source(signal_obj: dict) -> str:
    """منبع داده را از اولین تایم‌فریم موجود در جزئیات استخراج می‌کند."""
    try:
        details = signal_obj.get("raw_analysis_details", {}).get("details", {})
        if not details: return "N/A"
        first_tf_key = next(iter(details))
        return details[first_tf_key].get("source", "N/A")
    except (StopIteration, AttributeError):
        return "N/A"

def monitor_loop():
    """حلقه اصلی که به طور مداوم بازار را رصد می‌کند."""
    try:
        telegram = TelegramHandler()
        signal_cache = SignalCache(ttl_seconds=SIGNAL_CACHE_TTL_SECONDS)
        logging.info("Live Monitoring Worker started successfully with Duplicate Filter.")
        telegram.send_message("*✅ ربات مانیتورینگ پیشرفته (با فیلتر هوشمند) فعال شد.*")
    except ValueError as e:
        logging.error(f"Failed to start worker: {e}")
        return

    while True:
        logging.info("--- Starting New Monitoring Cycle ---")
        for symbol in SYMBOLS_TO_MONITOR:
            try:
                logging.info(f"Analyzing {symbol}...")
                signal_obj = _generate_signal_object(symbol, None, 'balanced')

                if not signal_obj:
                    logging.warning(f"Could not generate signal object for {symbol}.")
                    continue

                signal_type = signal_obj.get("signal_type")
                if signal_type and signal_type != "HOLD":
                    
                    if signal_cache.is_duplicate(symbol, signal_type):
                        logging.info(f"Duplicate signal '{signal_type}' for {symbol}. Skipping alert.")
                        continue
                    
                    signal_cache.store(symbol, signal_type)
                    
                    price = signal_obj.get("current_price", 0.0)
                    confidence = signal_obj.get("confidence", 0)
                    source = get_primary_source(signal_obj)
                    
                    message = (
                        f"🚨 *سیگنال جدید: {symbol}*\n\n"
                        f"*{signal_type}* @ `${price:,.2f}`\n"
                        f"اعتماد هوش مصنوعی: *{confidence}%*\n"
                        f"منبع داده: `{source}`"
                    )
                    telegram.send_message(message)
                    logging.info(f"Alert sent for {symbol}: {signal_type}")
                    time.sleep(5)

            except Exception as e:
                logging.error(f"Error processing symbol {symbol}: {e}", exc_info=True)
            
        logging.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds.")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    monitor_loop()
