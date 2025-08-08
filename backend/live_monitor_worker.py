import asyncio
import logging
import os
import django
import time
import json
import math
from typing import Dict, Tuple, List, Optional, Any
from asgiref.sync import sync_to_async

# --- تنظیمات پایه لاگ و راه‌اندازی جنگو (بدون تغییر) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s] - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pandas_ta").setLevel(logging.ERROR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

# --- ایمپورت‌های پروژه (بدون تغییر) ---
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler
from core.models import AnalysisSnapshot

# --- پارامترهای اصلی و کلاس SignalCache (بدون تغییر) ---
SYMBOLS_TO_MONITOR = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT']
TIMEFRAMES_TO_ANALYZE = ['15m', '1h', '4h']
POLL_INTERVAL_SECONDS = 900
SIGNAL_CACHE_TTL_MAP = {'15m': 3 * 3600, '1h': 6 * 3600, '4h': 12 * 3600, 'default': 4 * 3600}
class SignalCache:
    def __init__(self, ttl_map: Dict[str, int]): self._cache: Dict[Tuple[str, str, str], float] = {}; self.ttl_map = ttl_map
    def is_duplicate(self, symbol: str, timeframe: str, direction: str) -> bool:
        key = (symbol, timeframe, direction); ttl = self.ttl_map.get(timeframe, self.ttl_map['default'])
        if key in self._cache and (time.time() - self._cache[key]) < ttl:
            remaining_time = ((self._cache[key] + ttl) - time.time()) / 60
            logger.info(f"Duplicate signal {key} found. Cooldown active for {remaining_time:.1f} more minutes.")
            return True
        return False
    def store_signal(self, symbol: str, timeframe: str, direction: str):
        key = (symbol, timeframe, direction); self._cache[key] = time.time(); logger.info(f"Signal {key} stored in cache.")

def sanitize_for_json(data: Any) -> Any:
    if isinstance(data, dict): return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list): return [sanitize_for_json(i) for i in data]
    elif isinstance(data, float) and (math.isnan(data) or math.isinf(data)): return None
    return data

@sync_to_async
def save_analysis_snapshot(symbol: str, timeframe: str, package: Dict[str, Any]):
    # ✨ --- کد دیباگ جدید برای بررسی نوع داده‌ها --- ✨
    logger.info("--- DEBUG: Checking types in analysis package before saving ---")
    full_analysis_data = package.get("full_analysis", {})
    if isinstance(full_analysis_data, dict):
        for key, value in full_analysis_data.items():
            # ما نوع داده هر بخش از تحلیل را چاپ می‌کنیم
            logger.info(f"Analysis Key: '{key}', Value Type: {type(value)}")
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    logger.info(f"  -> Sub-Key: '{sub_key}', Sub-Value Type: {type(sub_value)}")
    # ✨ --- پایان کد دیباگ --- ✨
    
    try:
        status = package.get("status", "NEUTRAL")
        full_analysis = package.get("full_analysis", {})
        signal_data = package if status == "SUCCESS" else None
        
        sanitized_full_analysis = sanitize_for_json(full_analysis)
        sanitized_signal_package = sanitize_for_json(signal_data)
        
        snapshot, created = AnalysisSnapshot.objects.update_or_create(
            symbol=symbol,
            timeframe=timeframe,
            defaults={
                'status': status,
                'full_analysis': sanitized_full_analysis,
                'signal_package': sanitized_signal_package
            }
        )
        if created: logger.info(f"Created new AnalysisSnapshot for {symbol} {timeframe}.")
        else: logger.info(f"Updated AnalysisSnapshot for {symbol} {timeframe}.")
    except Exception as e:
        logger.error(f"Failed to save AnalysisSnapshot for {symbol} {timeframe}: {e}", exc_info=True)

# ... (بقیه فایل شامل توابع analyze_and_alert و main_loop بدون تغییر باقی می‌ماند) ...
async def analyze_and_alert(fetcher: ExchangeFetcher, orchestrator: MasterOrchestrator, telegram: TelegramHandler, cache: SignalCache, symbol: str, timeframe: str):
    try:
        logger.info(f"Fetching data for {symbol} on {timeframe}..."); df, source = await fetcher.get_first_successful_klines(symbol, timeframe, limit=300)
        if df is None or df.empty: logger.warning(f"Could not fetch data for {symbol} on {timeframe}."); return
        logger.info(f"Data for {symbol} fetched from {source}. Running full pipeline..."); final_signal_package = orchestrator.run_full_pipeline(df, symbol, timeframe)
        if final_signal_package: await save_analysis_snapshot(symbol, timeframe, final_signal_package)
        if final_signal_package and final_signal_package.get("status") == "SUCCESS":
            base_signal = final_signal_package.get("base_signal", {}); direction = base_signal.get("direction")
            if direction and not cache.is_duplicate(symbol, timeframe, direction):
                adapter = SignalAdapter(signal_package=final_signal_package); message = adapter.to_telegram_message()
                logger.info(f"🚀🚀 SIGNAL DETECTED! Preparing to send alert for {symbol} {timeframe} {direction} 🚀🚀")
                success = await telegram.send_message_async(message)
                if success: cache.store_signal(symbol, timeframe, direction)
    except Exception as e: logger.error(f"An error occurred during analysis for {symbol} {timeframe}: {e}", exc_info=True)
async def main_loop():
    config = {};
    try:
        with open('config.json', 'r', encoding='utf-8') as f: config = json.load(f)
        logger.info("Configuration file 'config.json' loaded successfully.")
    except FileNotFoundError: logger.error("FATAL: 'config.json' not found. The application will not run correctly."); return
    except json.JSONDecodeError: logger.error("FATAL: 'config.json' is not a valid JSON file."); return
    fetcher = ExchangeFetcher(); orchestrator = MasterOrchestrator(config=config); telegram = TelegramHandler(); signal_cache = SignalCache(ttl_map=SIGNAL_CACHE_TTL_MAP); version = orchestrator.ENGINE_VERSION
    logger.info("======================================================"); logger.info(f"  AiSignalPro Live Monitoring Worker (v{version}) has started!"); logger.info("======================================================")
    await telegram.send_message_async(f"✅ *AiSignalPro Bot (v{version} - DB Integrated) is now LIVE!*")
    while True:
        logger.info("--- Starting new full monitoring cycle ---"); tasks = [analyze_and_alert(fetcher, orchestrator, telegram, signal_cache, symbol, timeframe) for symbol in SYMBOLS_TO_MONITOR for timeframe in TIMEFRAMES_TO_ANALYZE]; await asyncio.gather(*tasks)
        logger.info(f"--- Full cycle finished. Sleeping for {POLL_INTERVAL_SECONDS} seconds... ---"); await asyncio.sleep(POLL_INTERVAL_SECONDS)
if __name__ == "__main__":
    try: asyncio.run(main_loop())
    except KeyboardInterrupt: logger.info("Bot stopped by user.")
    except Exception as e: logger.critical(f"A fatal error occurred in the main runner: {e}", exc_info=True)

