import asyncio
import logging
import os
import django
import time
import json
from typing import Dict, Tuple, List, Optional

# --- تنظیمات پایه لاگ قبل از هر کاری ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s] - %(message)s')
logging.getLogger("pandas_ta").setLevel(logging.ERROR)

# --- راه‌اندازی جنگو ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

# --- پارامترهای اصلی مانیتورینگ ---
SYMBOLS_TO_MONITOR = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT']
TIMEFRAMES_TO_ANALYZE = ['15m', '1h', '4h']
POLL_INTERVAL_SECONDS = 900 # 15 دقیقه

# --- تنظیمات کش سیگنال برای جلوگیری از ارسال تکراری ---
SIGNAL_CACHE_TTL_MAP = {
    '15m': 3 * 3600,  # 3 ساعت
    '1h': 6 * 3600,   # 6 ساعت
    '4h': 12 * 3600,  # 12 ساعت
    'default': 4 * 3600
}

class SignalCache:
    """
    یک کلاس ساده برای مدیریت کش سیگنال‌ها تا از ارسال پیام‌های تکراری جلوگیری شود.
    """
    def __init__(self, ttl_map: Dict[str, int]):
        self._cache: Dict[Tuple[str, str, str], float] = {}
        self.ttl_map = ttl_map

    def is_duplicate(self, symbol: str, timeframe: str, direction: str) -> bool:
        """
        چک می‌کند آیا سیگنال مشابهی اخیراً ارسال شده است یا خیر.
        """
        key = (symbol, timeframe, direction)
        ttl = self.ttl_map.get(timeframe, self.ttl_map['default'])
        
        if key in self._cache and (time.time() - self._cache[key]) < ttl:
            remaining_time = ((self._cache[key] + ttl) - time.time()) / 60
            logging.info(f"Duplicate signal {key} found. Cooldown active for {remaining_time:.1f} more minutes.")
            return True
        return False

    def store_signal(self, symbol: str, timeframe: str, direction: str):
        """
        یک سیگنال جدید را در کش ذخیره می‌کند.
        """
        key = (symbol, timeframe, direction)
        self._cache[key] = time.time()
        logging.info(f"Signal {key} stored in cache.")

async def analyze_and_alert(fetcher: ExchangeFetcher, orchestrator: MasterOrchestrator, telegram: TelegramHandler, cache: SignalCache, symbol: str, timeframe: str):
    """
    تابع اصلی که برای هر جفت‌ارز/تایم‌فریم اجرا می‌شود: داده‌ها را گرفته، تحلیل کرده و در صورت وجود سیگنال، هشدار ارسال می‌کند.
    """
    try:
        logging.info(f"Fetching data for {symbol} on {timeframe}...")
        df, source = await fetcher.get_first_successful_klines(symbol, timeframe, limit=300) # لیمیت بیشتر برای تحلیل‌های ZigZag/Fibonacci
        
        if df is None or df.empty:
            logging.warning(f"Could not fetch data for {symbol} on {timeframe}.")
            return

        logging.info(f"Data for {symbol} fetched from {source}. Running full pipeline...")
        final_signal_package = orchestrator.run_full_pipeline(df, symbol, timeframe)
        
        if final_signal_package:
            base_signal = final_signal_package.get("base_signal", {})
            direction = base_signal.get("direction")

            if direction and not cache.is_duplicate(symbol, timeframe, direction):
                adapter = SignalAdapter(signal_package=final_signal_package)
                message = adapter.to_telegram_message()
                logging.info(f"🚀🚀 SIGNAL DETECTED! Preparing to send alert for {symbol} {timeframe} {direction} 🚀🚀")
                success = await telegram.send_message_async(message)
                if success:
                    cache.store_signal(symbol, timeframe, direction)
    except Exception as e:
        logging.error(f"An error occurred during analysis for {symbol} {timeframe}: {e}", exc_info=True)

async def main_loop():
    """
    حلقه اصلی برنامه که به صورت مداوم اجرا می‌شود.
    """
    config = {}
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info("Configuration file 'config.json' loaded successfully.")
    except FileNotFoundError:
        logger.error("FATAL: 'config.json' not found. The application will not run correctly.")
        return
    except json.JSONDecodeError:
        logger.error("FATAL: 'config.json' is not a valid JSON file.")
        return

    fetcher = ExchangeFetcher()
    orchestrator = MasterOrchestrator(config=config)
    telegram = TelegramHandler()
    signal_cache = SignalCache(ttl_map=SIGNAL_CACHE_TTL_MAP)
    
    version = orchestrator.ENGINE_VERSION
    logging.info("======================================================")
    logging.info(f"  AiSignalPro Live Monitoring Worker (v{version}) has started!")
    logging.info("======================================================")
    await telegram.send_message_async(f"✅ *AiSignalPro Bot (v{version} - Fully Integrated) is now LIVE!*")
    
    while True:
        logging.info("--- Starting new full monitoring cycle ---")
        tasks = [
            analyze_and_alert(fetcher, orchestrator, telegram, signal_cache, symbol, timeframe)
            for symbol in SYMBOLS_TO_MONITOR
            for timeframe in TIMEFRAMES_TO_ANALYZE
        ]
        await asyncio.gather(*tasks)
        logging.info(f"--- Full cycle finished. Sleeping for {POLL_INTERVAL_SECONDS} seconds... ---")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.critical(f"A fatal error occurred in the main runner: {e}", exc_info=True)
