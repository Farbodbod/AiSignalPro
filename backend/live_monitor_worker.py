# live_monitor_worker.py (v3.0 - Configurable Logging Edition)

import asyncio
import logging
import os
import django
import time
import json
from typing import Dict, Tuple, List, Any, Optional
import pandas as pd
from asgiref.sync import sync_to_async

# ✅ NOTE: The basicConfig call is now moved inside main_loop to be configured dynamically.
logger = logging.getLogger(__name__)

# --- Django Setup and other imports remain the same ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler
from core.models import AnalysisSnapshot
from core.utils import convert_numpy_types

class SignalCache:
    # ... (کد این کلاس بدون تغییر است)
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
    # ... (کد این تابع بدون تغییر است)
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


async def main_loop():
    try:
        with open('config.json', 'r', encoding='utf-8') as f: config = json.load(f)
    except Exception as e:
        # Logging is not configured yet, so we use print for this critical error
        print(f"FATAL: Could not load or parse 'config.json'. Error: {e}"); return

    # --- ✅ NEW: Dynamic Logging Configuration ---
    general_config = config.get("general", {})
    log_level_str = general_config.get("log_level", "INFO").upper()
    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level = log_levels.get(log_level_str, logging.INFO) # Default to INFO if invalid
    
    # Configure the root logger with the level from config
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s] - %(message)s', force=True)
    logging.getLogger("pandas_ta").setLevel(logging.ERROR) # Keep this one quiet
    # --- End of New Logging Configuration ---

    symbols = general_config.get("symbols_to_monitor", ['BTC/USDT'])
    timeframes = general_config.get("timeframes_to_analyze", ['5m', '15m', '1h', '4h', '1d'])
    poll_interval = general_config.get("poll_interval_seconds", 300)
    max_concurrent = general_config.get("max_concurrent_tasks", 5)
    default_kline_limit = general_config.get("fetcher_limit", 500)

    fetcher = ExchangeFetcher(config=config.get("exchange_settings", {}))
    orchestrator = MasterOrchestrator(config=config)
    telegram = TelegramHandler()
    cache = SignalCache(ttl_map_hours=config.get("signal_cache", {}).get("ttl_map_hours", {}), 
                        default_ttl_hours=config.get("signal_cache", {}).get("default_ttl_hours", 4))
    
    version = orchestrator.ENGINE_VERSION
    analysis_state: Dict[Tuple[str, str], pd.DataFrame] = {}

    logger.info("="*50); logger.info(f"  AiSignalPro Live Worker (v{version}) - Final Architecture!"); 
    logger.info(f"  Log Level set to: {log_level_str}");
    logger.info(f"  Monitoring {len(symbols)} symbols on {len(timeframes)} timeframes."); 
    logger.info("="*50)
    await telegram.send_message_async(f"✅ *AiSignalPro Bot (v{version}) is LIVE!* (Log Level: {log_level_str})")
    
    semaphore = asyncio.Semaphore(max_concurrent)
    cycle_count = 0
    while True:
        cycle_count += 1
        start_time = time.time()
        logger.info(f"--- Starting Cycle #{cycle_count} ---")
        
        # --- Phase 1: Analysis ---
        logger.info(f"[Phase 1/2] Running analysis for all symbols and timeframes...")
        global_context: Dict[str, Dict[str, Any]] = {s: {} for s in symbols}
        new_states: Dict[Tuple[str, str], pd.DataFrame] = {}

        analysis_tasks = []
        for symbol in symbols:
            for timeframe in timeframes:
                async def run_single_analysis(sym, tf):
                    async with semaphore:
                        try:
                            state_key, previous_df = (sym, tf), analysis_state.get((sym, tf))
                            kline_limit = default_kline_limit 
                            
                            df, source = await fetcher.get_first_successful_klines(sym, tf, limit=kline_limit)
                            if df is None or df.empty:
                                logger.warning(f"Could not fetch data for {sym} on {tf}. Skipping analysis.")
                                return

                            analysis_result, new_state_df = orchestrator.run_analysis_pipeline(df, sym, tf, previous_df=previous_df)
                            
                            if analysis_result:
                                global_context[sym][tf] = analysis_result
                            if new_state_df is not None and not new_state_df.empty:
                                new_states[state_key] = new_state_df
                        except Exception as e:
                             logger.error(f"Error in analysis phase for {sym}@{tf}: {e}", exc_info=True)
                
                analysis_tasks.append(run_single_analysis(symbol, timeframe))
        
        await asyncio.gather(*analysis_tasks)
        
        analysis_state.update(new_states)
        logger.info(f"[Phase 1/2] Analysis phase complete.")

        # --- Phase 2: Strategy Execution ---
        logger.info(f"[Phase 2/2] Running strategies with global context...")
        strategy_tasks = []
        for symbol in symbols:
            if symbol not in global_context: continue
            for timeframe in timeframes:
                if timeframe not in global_context[symbol]: continue

                async def run_single_strategy(sym, tf):
                    async with semaphore:
                        try:
                            primary_analysis = global_context[sym][tf]
                            htf_context = global_context[sym]

                            final_signal_package = orchestrator.run_strategy_pipeline(primary_analysis, htf_context, sym, tf)

                            if final_signal_package:
                                await save_analysis_snapshot(sym, tf, final_signal_package)
                            
                            if final_signal_package and final_signal_package.get("status") == "SUCCESS":
                                base_signal = final_signal_package.get("base_signal", {})
                                direction = base_signal.get("direction")
                                if direction and not cache.is_duplicate(sym, tf, direction):
                                    adapter = SignalAdapter(signal_package=final_signal_package)
                                    message = adapter.to_telegram_message()
                                    logger.info(f"🚀🚀 SIGNAL DETECTED! Preparing to send alert for {sym} {tf} {direction} 🚀🚀")
                                    success = await telegram.send_message_async(message)
                                    if success:
                                        cache.store_signal(sym, tf, direction)
                        except Exception as e:
                            logger.error(f"Error in strategy phase for {sym}@{tf}: {e}", exc_info=True)
                
                strategy_tasks.append(run_single_strategy(symbol, timeframe))

        await asyncio.gather(*strategy_tasks)
        
        cycle_duration = time.time() - start_time
        logger.info(f"--- Cycle #{cycle_count} finished in {cycle_duration:.2f} seconds. Sleeping for {poll_interval} seconds... ---")
        await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"A fatal error occurred in the main runner: {e}", exc_info=True)

