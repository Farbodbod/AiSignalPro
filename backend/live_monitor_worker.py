import asyncio
import logging
import os
import django
import time
import json
import math
from typing import Dict, Tuple, List, Optional, Any
from asgiref.sync import sync_to_async

# --- تنظیمات پایه لاگ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pandas_ta").setLevel(logging.ERROR)

# --- راه‌اندازی جنگو ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

# --- ایمپورت‌های پروژه ---
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler
from core.models import AnalysisSnapshot
# فرض بر این است که این تابع در فایل utils شما قرار دارد
from core.utils import convert_numpy_types 

class SignalCache:
    """ یک کلاس ساده برای جلوگیری از ارسال سیگنال‌های تکراری. """
    def __init__(self, ttl_map: Dict[str, int]):
        self._cache: Dict[Tuple[str, str, str], float] = {}
        self.ttl_map = ttl_map

    def is_duplicate(self, symbol: str, timeframe: str, direction: str) -> bool:
        key = (symbol, timeframe, direction)
        ttl = self.ttl_map.get(timeframe, self.ttl_map.get('default', 3600))
        if key in self._cache and (time.time() - self._cache[key]) < ttl:
            remaining_time = ((self._cache[key] + ttl) - time.time()) / 60
            logger.info(f"Duplicate signal {key} found. Cooldown active for {remaining_time:.1f} more minutes.")
            return True
        return False

    def store_signal(self, symbol: str, timeframe: str, direction: str):
        key = (symbol, timeframe, direction)
        self._cache[key] = time.time()
        logger.info(f"Signal {key} stored in cache.")

@sync_to_async
def save_analysis_snapshot(symbol: str, timeframe: str, package: Dict[str, Any]):
    """ نتایج تحلیل را به صورت آسنکرون در دیتابیس ذخیره می‌کند. """
    try:
        status = package.get("status", "NEUTRAL")
        
        # ✨ REFINEMENT: Use the more powerful numpy-safe converter
        sanitized_package = convert_numpy_types(package)
        
        full_analysis = sanitized_package.get("full_analysis", {})
        signal_data = sanitized_package if status == "SUCCESS" else None
        
        AnalysisSnapshot.objects.update_or_create(
            symbol=symbol,
            timeframe=timeframe,
            defaults={
                'status': status,
                'full_analysis': full_analysis,
                'signal_package': signal_data
            }
        )
        logger.info(f"AnalysisSnapshot for {symbol} {timeframe} saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save AnalysisSnapshot for {symbol} {timeframe}: {e}", exc_info=True)

async def analyze_and_alert(
    semaphore: asyncio.Semaphore, 
    fetcher: ExchangeFetcher, 
    orchestrator: MasterOrchestrator, 
    telegram: TelegramHandler, 
    cache: SignalCache, 
    symbol: str, 
    timeframe: str
):
    """
    پایپ‌لاین کامل تحلیل برای یک جفت‌ارز و تایم‌فریم، با کنترل همزمانی.
    """
    async with semaphore:
        try:
            logger.info(f"Fetching data for {symbol} on {timeframe}...")
            df, source = await fetcher.get_first_successful_klines(symbol, timeframe, limit=500)
            if df is None or df.empty or len(df) < 200: # Ensure enough data for all indicators
                logger.warning(f"Could not fetch sufficient data for {symbol} on {timeframe}.")
                return

            logger.info(f"Data for {symbol} on {timeframe} fetched from {source}. Running full pipeline...")
            final_signal_package = orchestrator.run_full_pipeline(df, symbol, timeframe)
            
            if final_signal_package:
                await save_analysis_snapshot(symbol, timeframe, final_signal_package)
            
            if final_signal_package and final_signal_package.get("status") == "SUCCESS":
                base_signal = final_signal_package.get("base_signal", {})
                direction = base_signal.get("direction")
                if direction and not cache.is_duplicate(symbol, timeframe, direction):
                    adapter = SignalAdapter(signal_package=final_signal_package)
                    message = adapter.to_telegram_message()
                    logger.info(f"🚀🚀 SIGNAL DETECTED! Preparing to send alert for {symbol} {timeframe} {direction} 🚀🚀")
                    success = await telegram.send_message_async(message)
                    if success:
                        cache.store_signal(symbol, timeframe, direction)
        except Exception as e:
            logger.error(f"An error occurred during analysis for {symbol} {timeframe}: {e}", exc_info=True)

async def main_loop():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info("Configuration file 'config.json' loaded successfully.")
    except Exception as e:
        logger.error(f"FATAL: Could not load or parse 'config.json'. Error: {e}")
        return

    # ✨ REFINEMENT: Load all operational parameters from the config file
    general_config = config.get("general", {})
    symbols = general_config.get("symbols_to_monitor", ['BTC/USDT'])
    timeframes = general_config.get("timeframes_to_analyze", ['1h'])
    poll_interval = general_config.get("poll_interval_seconds", 900)
    max_concurrent = general_config.get("max_concurrent_tasks", 5)

    fetcher = ExchangeFetcher()
    orchestrator = MasterOrchestrator(config=config)
    telegram = TelegramHandler()
    signal_cache = SignalCache(ttl_map=SIGNAL_CACHE_TTL_MAP)
    version = orchestrator.ENGINE_VERSION
    
    logger.info("======================================================")
    logger.info(f"  AiSignalPro Live Monitoring Worker (v{version}) has started!")
    logger.info(f"  Monitoring {len(symbols)} symbols on {len(timeframes)} timeframes.")
    logger.info(f"  Concurrency limit set to {max_concurrent} tasks.")
    logger.info("======================================================")
    await telegram.send_message_async(f"✅ *AiSignalPro Bot (v{version}) is now LIVE!*")
    
    # ✨ REFINEMENT: Create a semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)
    
    cycle_count = 0
    while True:
        cycle_count += 1
        logger.info(f"--- Starting new monitoring cycle #{cycle_count} ---")
        tasks = [
            analyze_and_alert(semaphore, fetcher, orchestrator, telegram, signal_cache, symbol, timeframe)
            for symbol in symbols
            for timeframe in timeframes
        ]
        await asyncio.gather(*tasks)
        logger.info(f"--- Cycle #{cycle_count} finished. Sleeping for {poll_interval} seconds... ---")
        await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"A fatal error occurred in the main runner: {e}", exc_info=True)
