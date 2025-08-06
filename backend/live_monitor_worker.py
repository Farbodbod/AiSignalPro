# engines/live_monitor_worker.py (v17.2 - با لاگ‌های تمیز)

import asyncio
import logging
import os
import django
import time
from typing import Dict, Tuple

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

SYMBOLS_TO_MONITOR = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT']
TIMEFRAMES_TO_ANALYZE = ['15m', '1h', '4h']
POLL_INTERVAL_SECONDS = 900

SIGNAL_CACHE_TTL_MAP = {
    '15m': 3 * 3600, '1h': 6 * 3600, '4h': 12 * 3600, 'default': 4 * 3600
}

# --- ✨ تغییر کلیدی: افزودن فیلتر برای تمیز کردن لاگ‌ها ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s] - %(message)s')
logging.getLogger("pandas_ta").setLevel(logging.ERROR)


class SignalCache:
    def __init__(self, ttl_map: Dict[str, int]):
        self._cache: Dict[Tuple[str, str, str], float] = {}
        self.ttl_map = ttl_map

    def is_duplicate(self, symbol: str, timeframe: str, direction: str) -> bool:
        key = (symbol, timeframe, direction)
        ttl = self.ttl_map.get(timeframe, self.ttl_map['default'])
        if key in self._cache and (time.time() - self._cache[key]) < ttl:
            logging.info(f"Duplicate signal {key} found. Cooldown active for {((self._cache[key] + ttl) - time.time()) / 60:.1f} minutes.")
            return True
        return False

    def store_signal(self, symbol: str, timeframe: str, direction: str):
        self._cache[key] = time.time()

async def analyze_and_alert(fetcher: ExchangeFetcher, orchestrator: MasterOrchestrator, telegram: TelegramHandler, cache: SignalCache, symbol: str, timeframe: str):
    try:
        logging.info(f"Fetching data for {symbol} on {timeframe}...")
        df, source = await fetcher.get_first_successful_klines(symbol, timeframe, limit=200)

        if df is None or df.empty:
            logging.warning(f"Could not fetch data for {symbol} on {timeframe}.")
            return

        logging.info(f"Data fetched from {source}. Running full pipeline for {symbol} on {timeframe}...")
        final_signal_package = orchestrator.run_full_pipeline(df, symbol, timeframe)

        if final_signal_package:
            base_signal = final_signal_package.get("base_signal", {})
            direction = base_signal.get("direction")

            if cache.is_duplicate(symbol, timeframe, direction):
                return
            
            adapter = SignalAdapter(signal_package=final_signal_package)
            message = adapter.to_telegram_message()
            
            logging.info(f"🚀🚀 SIGNAL DETECTED! Preparing to send alert for {symbol} {timeframe} {direction} 🚀🚀")
            success = await telegram.send_message_async(message)
            if success:
                cache.store_signal(symbol, timeframe, direction)
    
    except Exception as e:
        logging.error(f"An error occurred during analysis for {symbol} {timeframe}: {e}", exc_info=True)

async def main_loop():
    fetcher = ExchangeFetcher()
    orchestrator = MasterOrchestrator()
    telegram = TelegramHandler()
    signal_cache = SignalCache(ttl_map=SIGNAL_CACHE_TTL_MAP)

    logging.info("======================================================")
    logging.info(f"  AiSignalPro Live Monitoring Worker has started!")
    logging.info(f"  Version: 17.3 (Quality Control Edition)")
    logging.info("======================================================")
    await telegram.send_message_async("✅ *AiSignalPro Bot (v17.3) is now LIVE!*")

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

    await fetcher.close()

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.critical(f"A fatal error occurred in the main runner: {e}", exc_info=True)

