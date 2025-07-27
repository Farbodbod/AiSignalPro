# live_monitor_worker.py - نسخه نهایی و کامل

import time
import logging
from typing import Dict, Any

# برای اینکه این اسکریپت بتواند به تنظیمات و مدل‌های جنگو دسترسی داشته باشد
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

# حالا می‌توانیم ماژول‌های پروژه خود را وارد کنیم
from core.views import _generate_signal_object
from engines.telegram_handler import TelegramHandler

# ================================== تنظیمات ==================================
# در اینجا می‌توانید لیست ارزها و فاصله زمانی بین هر تحلیل کامل را مشخص کنید
SYMBOLS_TO_MONITOR = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
POLL_INTERVAL_SECONDS = 300  # تحلیل هر ۵ دقیقه یک بار
SIGNAL_CACHE_TTL_SECONDS = 1800  # هر سیگنال مشابه تا ۳۰ دقیقه دوباره ارسال نمی‌شود
# ===========================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SignalCache:
    """یک حافظه موقت برای جلوگیری از ارسال سیگنال‌های تکراری."""
    def __init__(self, ttl_seconds: int):
        self.cache: Dict[str, tuple] = {}
        self.ttl = ttl_seconds

    def is_duplicate(self, symbol: str, signal_type: str) -> bool:
        """بررسی می‌کند که آیا سیگنال جدید برای یک ارز تکراری است یا خیر."""
        now = time.time()
        if symbol in self.cache:
            last_signal, last_time = self.cache[symbol]
            if signal_type == last_signal and (now - last_time) < self.ttl:
                return True
        return False

    def store(self, symbol: str, signal_type: str):
        """سیگنال جدید را در حافظه ذخیره می‌کند."""
        self.cache[symbol] = (signal_type, time.time())

def format_professional_message(signal_obj: dict) -> str:
    """یک پیام تلگرام حرفه‌ای و پر از جزئیات می‌سازد."""
    signal_type = signal_obj.get("signal_type", "N/A")
    symbol = signal_obj.get("symbol", "N/A")
    price = signal_obj.get("current_price", 0.0)
    confidence = signal_obj.get("confidence", 0)
    risk = signal_obj.get("risk_level", "N/A")
    
    scores = signal_obj.get("scores", {})
    buy_score = scores.get("buy_score", 0)
    sell_score = scores.get("sell_score", 0)
    
    tags = ", ".join(signal_obj.get("tags", ["No specific factors"]))

    message = (
        f"SIGNAL ALERT: *{signal_type} {symbol}*\n"
        f"----------------------------------------\n"
        f"🔹 *Price:* `${price:,.2f}`\n"
        f"🔸 *AI Confidence:* {confidence}%\n"
        f"💣 *Risk Level:* `{risk.upper()}`\n"
        f"📈 *Buy Score:* {buy_score:.2f}\n"
        f"📉 *Sell Score:* {sell_score:.2f}\n"
        f"🔍 *Key Factors:* `{tags}`\n"
        f"----------------------------------------"
    )
    return message

def monitor_loop():
    """حلقه اصلی که به طور مداوم بازار را رصد می‌کند."""
    try:
        telegram = TelegramHandler()
        signal_cache = SignalCache(ttl_seconds=SIGNAL_CACHE_TTL_SECONDS)
        logging.info("Live Monitoring Worker started with Professional Formatting.")
        telegram.send_message("*✅ ربات مانیتورینگ حرفه‌ای فعال شد.*")
    except ValueError as e:
        logging.error(f"Failed to start worker due to config error: {e}")
        return

    while True:
        logging.info("--- Starting New Monitoring Cycle ---")
        for symbol in SYMBOLS_TO_MONITOR:
            try:
                logging.info(f"Analyzing {symbol}...")
                # فراخوانی تابع اصلی تولید سیگنال از `views`
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
                    
                    professional_message = format_professional_message(signal_obj)
                    
                    telegram.send_message(professional_message)
                    logging.info(f"Alert sent for {symbol}: {signal_type}")
                    time.sleep(5) # تاخیر کوتاه بین ارسال پیام‌ها

            except Exception as e:
                logging.error(f"Error processing symbol {symbol}: {e}", exc_info=True)
            
        logging.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds.")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    monitor_loop()

