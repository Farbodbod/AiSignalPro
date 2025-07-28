# live_monitor_worker.py (نسخه نهایی و اصلاح شده)

import time
import logging
import pandas as pd
import os
import django
import traceback

# --- راه‌اندازی اولیه Django برای دسترسی به مدل‌ها و تنظیمات ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

# --- وارد کردن ماژول‌های پروژه ---
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

# --- تنظیمات اصلی ربات ---
SYMBOLS_TO_MONITOR = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT', 'XRP-USDT']
POLL_INTERVAL_SECONDS = 600  # هر ۱۰ دقیقه یک بار
SIGNAL_CACHE_TTL_SECONDS = 3600  # سیگنال تکراری تا ۱ ساعت ارسال نمی‌شود

# --- تنظیمات لاگ‌گیری ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s'
)

class SignalCache:
    """کلاسی برای مدیریت و جلوگیری از ارسال سیگنال‌های تکراری."""
    def __init__(self, ttl_seconds: int):
        self.cache = {}
        self.ttl = ttl_seconds

    def is_duplicate(self, symbol: str, signal_type: str) -> bool:
        now = time.time()
        if symbol in self.cache:
            last_signal, last_time = self.cache[symbol]
            if signal_type == last_signal and (now - last_time) < self.ttl:
                return True
        return False

    def store(self, symbol: str, signal_type: str):
        self.cache[symbol] = (signal_type, time.time())

def format_professional_message(signal_obj: dict) -> str:
    """یک آبجکت سیگنال را به یک پیام تلگرام حرفه‌ای و خوانا تبدیل می‌کند."""
    signal_type = signal_obj.get("signal_type", "N/A")
    symbol = signal_obj.get("symbol", "N/A")
    price = signal_obj.get("current_price", 0.0)
    confidence = signal_obj.get("ai_confidence_percent", 0)
    risk = signal_obj.get("risk_level", "unknown")
    scores = signal_obj.get("scores", {})
    buy_score = scores.get("buy_score", 0)
    sell_score = scores.get("sell_score", 0)
    tags = ", ".join(signal_obj.get("tags", [])) or "N/A"

    emoji = "📈" if signal_type == "BUY" else "📉" if signal_type == "SELL" else "⏳"
    
    message = (
        f"{emoji} *SIGNAL: {signal_type} {symbol}*\n"
        f"----------------------------------------\n"
        f"🔹 *Price:* `${price:,.4f}`\n"
        f"🔸 *AI Confidence:* {confidence}%\n"
        f"💣 *Risk Level:* `{risk.upper()}`\n"
        f"📈 *Buy Score:* `{buy_score:.2f}`\n"
        f"📉 *Sell Score:* `{sell_score:.2f}`\n"
        f"🔍 *Key Factors:* `{tags}`"
    )
    return message
    
def _get_data_with_fallback_worker(fetcher, symbol, interval, limit, min_length):
    """داده‌ها را از منابع مختلف دریافت می‌کند تا پایداری ربات افزایش یابد."""
    for source in ['kucoin', 'mexc', 'okx', 'gateio']:
        try:
            kline_data = fetcher.get_klines(source=source, symbol=symbol, interval=interval, limit=limit)
            df = pd.DataFrame(kline_data)
            if not df.empty and len(df) >= min_length:
                logging.info(f"OK: Fetched {len(df)} candles from {source} for {symbol} @ {interval}.")
                return df, source
        except Exception as e:
            logging.warning(f"FAIL: Could not fetch from {source} for {symbol} ({interval}): {e}")
    return None, None

def monitor_loop():
    """حلقه اصلی ربات که به صورت مداوم بازار را رصد می‌کند."""
    try:
        telegram = TelegramHandler()
        signal_cache = SignalCache(ttl_seconds=SIGNAL_CACHE_TTL_SECONDS)
        orchestrator = MasterOrchestrator()
        fetcher = ExchangeFetcher()
        logging.info("Live Monitoring Worker started successfully.")
        telegram.send_message("✅ *ربات مانیتورینگ AiSignalPro (نسخه پایدار) فعال شد.*\nربات در حال رصد بازار است...")
    except Exception as e:
        logging.error(f"FATAL: Failed to initialize worker components: {e}", exc_info=True)
        return

    while True:
        logging.info("--- Starting New Monitoring Cycle ---")
        for symbol in SYMBOLS_TO_MONITOR:
            try:
                all_tf_analysis = {}
                timeframes_to_analyze = ['5m', '15m', '1h', '4h', '1d']
                
                for tf in timeframes_to_analyze:
                    limit = 300 if tf in ['1h', '4h', '1d'] else 100
                    min_length = 200 if tf in ['1h', '4h', '1d'] else 50
                    df, source = _get_data_with_fallback_worker(fetcher, symbol, tf, limit=limit, min_length=min_length)
                    if df is not None:
                        ## --- اصلاح شد: پارامتر symbol به اینجا اضافه شد --- ##
                        analysis = orchestrator.analyze_single_dataframe(df, tf, symbol=symbol)
                        analysis['source'] = source
                        all_tf_analysis[tf] = analysis
                
                if not all_tf_analysis:
                    logging.warning(f"Could not fetch enough data for {symbol} on any timeframe. Skipping.")
                    continue

                raw_orchestrator_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)
                
                adapter = SignalAdapter(analytics_output=raw_orchestrator_result, strategy='balanced')
                signal_obj = adapter.combine()
                
                if not signal_obj or not isinstance(signal_obj, dict):
                    logging.warning(f"Adapter did not produce a valid signal object for {symbol}. Skipping.")
                    continue

                signal_type = signal_obj.get("signal_type")
                if signal_type and signal_type.upper() != "HOLD":
                    if not signal_cache.is_duplicate(symbol, signal_type):
                        signal_cache.store(symbol, signal_type)
                        professional_message = format_professional_message(signal_obj)
                        telegram.send_message(professional_message)
                        logging.info(f"ALERT SENT for {symbol}: {signal_type}")
                        time.sleep(5)
                    else:
                        logging.info(f"Duplicate signal '{signal_type}' for {symbol}. Skipping alert.")
                else:
                    logging.info(f"Signal is HOLD for {symbol}. No alert.")

            except Exception as e:
                logging.error(f"Error processing symbol {symbol}: {e}")
                logging.error(traceback.format_exc())
            
        logging.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds.")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    monitor_loop()

