# live_monitor_worker.py (v4.1 - Resilient Gather)

import asyncio
import logging
import os
import django
import time
import json
from typing import Dict, Tuple, List, Any, Optional

import pandas as pd
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler
from core.models import AnalysisSnapshot
from core.utils import convert_numpy_types

class SignalCache:
    def __init__(self, ttl_map_hours: Dict[str, int], default_ttl_hours: int):
        self._cache: Dict[Tuple[str, str, str], float] = {}
        self.ttl_map_seconds = {tf: hours * 3600 for tf, hours in ttl_map_hours.items()}
        self.default_ttl_seconds = default_ttl_hours * 3600

    def is_duplicate(self, symbol: str, timeframe: str, direction: str) -> bool:
        key = (symbol, timeframe, direction); ttl = self.ttl_map_seconds.get(timeframe, self.default_ttl_seconds)
        if key in self._cache and (time.time() - self._cache[key]) < ttl:
            remaining = ((self._cache[key] + ttl) - time.time()) / 60
            logger.info(f"Duplicate signal {key} found. Cooldown: {remaining:.1f}m left.")
            return True
        return False

    def store_signal(self, symbol: str, timeframe: str, direction: str):
        self._cache[(symbol, timeframe, direction)] = time.time()
        logger.info(f"Signal {(symbol, timeframe, direction)} stored in cache.")

@sync_to_async
def save_analysis_snapshot(symbol: str, timeframe: str, package: Dict[str, Any]):
    try:
        status = package.get("status", "NEUTRAL"); sanitized_package = convert_numpy_types(package)
        full_analysis = sanitized_package.get("full_analysis", {}); signal_data = sanitized_package if status == "SUCCESS" else None
        AnalysisSnapshot.objects.update_or_create(symbol=symbol, timeframe=timeframe, defaults={'status': status, 'full_analysis': full_analysis, 'signal_package': signal_data})
        logger.info(f"AnalysisSnapshot for {symbol}@{timeframe} saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save AnalysisSnapshot for {symbol}@{timeframe}: {e}", exc_info=True)

async def run_single_analysis(symbol: str, timeframe: str, orchestrator: MasterOrchestrator, fetcher: ExchangeFetcher, analysis_state: Dict, global_context: Dict, new_states: Dict, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            state_key = (symbol, timeframe); previous_df = analysis_state.get(state_key)
            kline_limit = orchestrator.config.get("general", {}).get("fetcher_limit", 500)
            df, source = await fetcher.get_first_successful_klines(symbol, timeframe, limit=kline_limit)
            if df is None or df.empty:
                logger.warning(f"Could not fetch data for {symbol}@{timeframe}. Skipping analysis.")
                return
            analysis_result, new_state_df = await orchestrator.run_analysis_pipeline(df, symbol, timeframe, previous_df=previous_df)
            if analysis_result: global_context[symbol][timeframe] = analysis_result
            if new_state_df is not None and not new_state_df.empty: new_states[state_key] = new_state_df
        except Exception as e:
            # This exception will now be caught by gather and will not crash the cycle.
            logger.error(f"CRITICAL ERROR in analysis task for {symbol}@{timeframe}: {e}", exc_info=True)
            # Re-raise the exception so gather can capture it.
            raise

async def run_single_strategy(symbol: str, timeframe: str, orchestrator: MasterOrchestrator, global_context: Dict, cache: SignalCache, telegram: TelegramHandler, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            if symbol not in global_context or timeframe not in global_context[symbol]: return
            primary_analysis = global_context[symbol][timeframe]; htf_context = global_context[symbol]
            final_signal_package = await orchestrator.run_strategy_pipeline(primary_analysis, htf_context, symbol, timeframe)
            if final_signal_package: await save_analysis_snapshot(symbol, timeframe, final_signal_package)
            if final_signal_package and final_signal_package.get("status") == "SUCCESS":
                base_signal = final_signal_package.get("base_signal", {}); direction = base_signal.get("direction")
                if direction and not cache.is_duplicate(symbol, timeframe, direction):
                    adapter = SignalAdapter(signal_package=final_signal_package); message = adapter.to_telegram_message()
                    logger.info(f"🚀🚀 SIGNAL DETECTED! Preparing alert for {symbol}@{timeframe} {direction}")
                    success = await telegram.send_message_async(message)
                    if success: cache.store_signal(symbol, timeframe, direction)
        except Exception as e:
            # This exception will also be caught by gather.
            logger.error(f"CRITICAL ERROR in strategy task for {symbol}@{timeframe}: {e}", exc_info=True)
            raise

async def main_loop():
    try:
        with open('config.json', 'r', encoding='utf-8') as f: config = json.load(f)
    except Exception as e:
        print(f"FATAL: Could not load or parse 'config.json'. Error: {e}"); return

    general_config = config.get("general", {})
    log_level_str = general_config.get("log_level", "INFO").upper(); log_levels = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
    root_log_level = log_levels.get(log_level_str, logging.INFO)
    logging.basicConfig(level=root_log_level, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s', force=True)
    logging.getLogger("core").setLevel(root_log_level); logging.getLogger("engines").setLevel(root_log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    symbols = general_config.get("symbols_to_monitor", []); timeframes = general_config.get("timeframes_to_analyze", [])
    poll_interval, max_concurrent = general_config.get("poll_interval_seconds", 300), general_config.get("max_concurrent_tasks", 5)

    fetcher = ExchangeFetcher(config=config.get("exchange_settings", {})); orchestrator = MasterOrchestrator(config=config)
    telegram = TelegramHandler(); cache = SignalCache(ttl_map_hours=config.get("signal_cache", {}).get("ttl_map_hours", {}), default_ttl_hours=config.get("signal_cache", {}).get("default_ttl_hours", 4))

    version = orchestrator.ENGINE_VERSION; analysis_state: Dict[Tuple[str, str], pd.DataFrame] = {}

    logger.info("=" * 50); logger.info(f"  AiSignalPro Live Worker (v{version}) - Fully Async & Hardened"); logger.info(f"  Root Log Level set to: {logging.getLevelName(root_log_level)}"); logger.info(f"  Monitoring {len(symbols)} symbols on {len(timeframes)} timeframes."); logger.info("=" * 50)
    await telegram.send_message_async(f"✅ *AiSignalPro Bot (v{version}) is LIVE!* (Log Level: {log_level_str})")

    semaphore = asyncio.Semaphore(max_concurrent); cycle_count = 0
    while True:
        cycle_count += 1; start_time = time.time()
        logger.info(f"--- Starting Cycle #{cycle_count} ---")

        global_context = {s: {} for s in symbols}; new_states: Dict = {}
        
        logger.info(f"[Phase 1/2] Creating analysis tasks...")
        analysis_tasks = [run_single_analysis(s, tf, orchestrator, fetcher, analysis_state, global_context, new_states, semaphore) for s in symbols for tf in timeframes]
        # ✅ THE BULLETPROOF FIX: Exceptions in single tasks will no longer crash the entire cycle.
        analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        analysis_state.update(new_states); logger.info(f"[Phase 1/2] Analysis phase complete.")

        logger.info(f"[Phase 2/2] Creating strategy tasks...")
        strategy_tasks = [run_single_strategy(s, tf, orchestrator, global_context, cache, telegram, semaphore) for s in symbols for tf in timeframes]
        # ✅ THE BULLETPROOF FIX: Also applied to the strategy phase for maximum resilience.
        strategy_results = await asyncio.gather(*strategy_tasks, return_exceptions=True)
        
        # Optional: You can add a loop here to log any exceptions that were caught by `gather`.
        for i, result in enumerate(analysis_results):
            if isinstance(result, Exception):
                logger.error(f"Caught exception in analysis task {i}: {result}")
        for i, result in enumerate(strategy_results):
            if isinstance(result, Exception):
                logger.error(f"Caught exception in strategy task {i}: {result}")
        
        cycle_duration = time.time() - start_time
        logger.info(f"--- Cycle #{cycle_count} finished in {cycle_duration:.2f} seconds. Sleeping for {poll_interval} seconds... ---")
        await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    try: asyncio.run(main_loop())
    except KeyboardInterrupt: logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"A fatal error occurred in the main runner: {e}", exc_info=True)
