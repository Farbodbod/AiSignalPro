import asyncio
import logging
import os
import django
import time
import json
from typing import Dict, Tuple, List, Any, Optional
import pandas as pd
from asgiref.sync import sync_to_async

# --- All setup and helper classes/functions remain the same ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pandas_ta").setLevel(logging.ERROR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler
from core.models import AnalysisSnapshot
from core.utils import convert_numpy_types

class SignalCache:
    # Unchanged
    def __init__(self, ttl_map_hours: Dict[str, int], default_ttl_hours: int):
        self._cache: Dict[Tuple[str, str, str], float] = {}
        self.ttl_map_seconds = {tf: hours * 3600 for tf, hours in ttl_map_hours.items()}
        self.default_ttl_seconds = default_ttl_hours * 3600
    def is_duplicate(self, symbol: str, timeframe: str, direction: str) -> bool:
        key = (symbol, timeframe, direction)
        ttl = self.ttl_map_seconds.get(timeframe, self.default_ttl_seconds)
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
    # Unchanged
    try:
        status = package.get("status", "NEUTRAL")
        sanitized_package = convert_numpy_types(package)
        full_analysis = sanitized_package.get("full_analysis", {})
        signal_data = sanitized_package if status == "SUCCESS" else None
        AnalysisSnapshot.objects.update_or_create(
            symbol=symbol, timeframe=timeframe,
            defaults={'status': status, 'full_analysis': full_analysis, 'signal_package': signal_data}
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
    timeframe: str,
    kline_limit: int,
    analysis_state: Dict[Tuple[str, str], pd.DataFrame],
    previous_df: Optional[pd.DataFrame]
):
    # This function's logic remains correct and unchanged
    async with semaphore:
        state_key = (symbol, timeframe)
        try:
            logger.info(f"Fetching {kline_limit} klines for {symbol} on {timeframe}...")
            df, source = await fetcher.get_first_successful_klines(symbol, timeframe, limit=kline_limit)
            min_rows_for_analysis = 5 if previous_df is not None else 200
            if df is None or df.empty or len(df) < min_rows_for_analysis:
                logger.warning(f"Could not fetch sufficient recent data for {symbol} on {timeframe}.")
                return
            final_signal_package, new_state = orchestrator.run_full_pipeline(df, symbol, timeframe, previous_df=previous_df)
            if new_state is not None and not new_state.empty:
                analysis_state[state_key] = new_state
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
    # ... Config loading is the same ...
    try:
        with open('config.json', 'r', encoding='utf-8') as f: config = json.load(f)
    except Exception as e:
        logger.error(f"FATAL: Could not load or parse 'config.json'. Error: {e}"); return

    general_config = config.get("general", {})
    symbols = general_config.get("symbols_to_monitor", ['BTC/USDT'])
    timeframes = general_config.get("timeframes_to_analyze", ['1h'])
    poll_interval = general_config.get("poll_interval_seconds", 900)
    max_concurrent = general_config.get("max_concurrent_tasks", 5)
    
    kline_limit_map = general_config.get("kline_limit_map", {})
    default_kline_limit = general_config.get("fetcher_limit", 400)

    # ✅ GENIUS UPGRADE: Timeframe to seconds mapping for dynamic calculation
    timeframe_seconds_map = {
        '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
        '1h': 3600, '2h': 7200, '4h': 14400, '1d': 86400
    }
    
    fetcher = ExchangeFetcher()
    orchestrator = MasterOrchestrator(config=config)
    telegram = TelegramHandler()
    cache = SignalCache(ttl_map_hours=config.get("signal_cache", {}).get("ttl_map_hours", {}), 
                        default_ttl_hours=config.get("signal_cache", {}).get("default_ttl_hours", 4))
    
    version = orchestrator.ENGINE_VERSION
    analysis_state: Dict[Tuple[str, str], pd.DataFrame] = {}

    logger.info("="*50); logger.info(f"  AiSignalPro Live Monitoring Worker (v{version}) - GENIUS STATEFUL MODE!"); 
    logger.info(f"  Monitoring {len(symbols)} symbols on {len(timeframes)} timeframes."); 
    logger.info("="*50)
    await telegram.send_message_async(f"✅ *AiSignalPro Bot (v{version}) is now LIVE! (Genius Stateful Mode)*")
    
    semaphore = asyncio.Semaphore(max_concurrent)
    cycle_count = 0
    while True:
        cycle_count += 1
        logger.info(f"--- Starting new monitoring cycle #{cycle_count} ---")
        
        tasks = []
        for symbol in symbols:
            for timeframe in timeframes:
                state_key = (symbol, timeframe)
                previous_df = analysis_state.get(state_key)
                
                # ✅ GENIUS UPGRADE: Dynamic kline limit calculation
                if previous_df is not None and not previous_df.empty:
                    last_timestamp_ms = previous_df.index[-1].value // 1_000_000
                    current_timestamp_ms = int(time.time() * 1000)
                    time_diff_seconds = (current_timestamp_ms - last_timestamp_ms) / 1000
                    
                    timeframe_duration_seconds = timeframe_seconds_map.get(timeframe, 3600) # Default to 1h
                    
                    # Calculate how many candles we might have missed
                    missing_candles = int(time_diff_seconds / timeframe_duration_seconds)
                    
                    # Add a safety buffer and ensure it's a reasonable number
                    kline_limit = missing_candles + 10 # 10 candles as a safety buffer
                    kline_limit = min(kline_limit, default_kline_limit) # Don't request more than the full load
                else:
                    # If no history, fetch the full amount
                    kline_limit = kline_limit_map.get(timeframe, default_kline_limit)

                task = analyze_and_alert(
                    semaphore, fetcher, orchestrator, telegram, cache, 
                    symbol, timeframe, kline_limit,
                    analysis_state, previous_df
                )
                tasks.append(task)

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
