# live_monitor_worker.py (v5.2 - Refined Logging Config & Full Code)
import asyncio
import logging
import os
import django
import time
import json
import sys
from typing import Dict, Tuple, List, Any, Optional
from collections import Counter
from datetime import datetime, timezone

# --- World-Class Logging Imports ---
import structlog
from rich.logging import RichHandler
# ------------------------------------

import pandas as pd
from asgiref.sync import sync_to_async

# Note: We get the logger via structlog now.
logger = structlog.get_logger()

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
        key, ttl = (symbol, timeframe, direction), self.ttl_map_seconds.get(timeframe, self.default_ttl_seconds)
        if key in self._cache and (time.time() - self._cache[key]) < ttl:
            remaining = ((self._cache[key] + ttl) - time.time()) / 60
            logger.info("Duplicate signal found", key=key, cooldown_minutes_left=f"{remaining:.1f}")
            return True
        return False
    def store_signal(self, symbol: str, timeframe: str, direction: str):
        key = (symbol, timeframe, direction)
        self._cache[key] = time.time()
        logger.info("Signal stored in cache", key=key)

@sync_to_async
def save_analysis_snapshot(symbol: str, timeframe: str, package: Dict[str, Any]):
    try:
        status = package.get("status", "NEUTRAL")
        sanitized_package = convert_numpy_types(package)
        full_analysis = sanitized_package.get("full_analysis", {})
        signal_data = sanitized_package if status == "SUCCESS" else None
        AnalysisSnapshot.objects.update_or_create(
            symbol=symbol, timeframe=timeframe,
            defaults={'status': status, 'full_analysis': full_analysis, 'signal_package': signal_data}
        )
        logger.debug("AnalysisSnapshot saved", symbol=symbol, timeframe=timeframe)
    except Exception as e:
        logger.error("Failed to save AnalysisSnapshot", symbol=symbol, timeframe=timeframe, error=str(e), exc_info=True)

async def run_single_analysis(symbol: str, timeframe: str, orchestrator: MasterOrchestrator, fetcher: ExchangeFetcher, analysis_state: Dict, global_context: Dict, new_states: Dict, semaphore: asyncio.Semaphore) -> Tuple[str, str, str]:
    task_id = f"{symbol}@{timeframe}"
    async with semaphore:
        try:
            logger.debug("Starting analysis task", task_id=task_id)
            state_key, previous_df = (symbol, timeframe), analysis_state.get((symbol, timeframe))
            kline_limit = orchestrator.config.get("general", {}).get("fetcher_limit", 500)
            df, source = await fetcher.get_first_successful_klines(symbol, timeframe, limit=kline_limit)
            if df is None or df.empty:
                logger.warning("Could not fetch kline data.", task_id=task_id, source=source)
                return ("warning", task_id, "Missing kline data")
            analysis_result, new_state_df = await orchestrator.run_analysis_pipeline(df, symbol, timeframe, previous_df=previous_df)
            if analysis_result: global_context[symbol][timeframe] = analysis_result
            if new_state_df is not None and not new_state_df.empty: new_states[state_key] = new_state_df
            logger.debug("Analysis task complete", task_id=task_id)
            return ("success", task_id, "OK")
        except Exception as e:
            logger.error("Error in analysis phase", task_id=task_id, error=str(e), exc_info=True)
            return ("error", task_id, str(e))

async def run_single_strategy(symbol: str, timeframe: str, orchestrator: MasterOrchestrator, global_context: Dict, cache: SignalCache, telegram: TelegramHandler, semaphore: asyncio.Semaphore) -> Tuple[str, Optional[Dict]]:
    task_id = f"{symbol}@{timeframe}"
    async with semaphore:
        try:
            if symbol not in global_context or timeframe not in global_context[symbol]: return ("skipped", None)
            primary_analysis, htf_context = global_context[symbol][timeframe], global_context[symbol]
            final_signal_package = await orchestrator.run_strategy_pipeline(primary_analysis, htf_context, symbol, timeframe)
            if final_signal_package: await save_analysis_snapshot(symbol, timeframe, final_signal_package)
            if final_signal_package and final_signal_package.get("status") == "SUCCESS":
                base_signal, direction = final_signal_package.get("base_signal", {}), base_signal.get("direction")
                if direction and not cache.is_duplicate(symbol, timeframe, direction):
                    adapter, message = SignalAdapter(signal_package=final_signal_package), adapter.to_telegram_message()
                    logger.info(f"🚀🚀 SIGNAL DETECTED! Preparing alert for {symbol}@{timeframe} {direction}")
                    success = await telegram.send_message_async(message)
                    if success:
                        cache.store_signal(symbol, timeframe, direction); return ("signal_sent", {"symbol": symbol, "timeframe": timeframe, "direction": direction})
                    else:
                        return ("send_failed", {"symbol": symbol, "timeframe": timeframe, "direction": direction})
            return ("no_signal", None)
        except Exception as e:
            logger.error("Error in strategy phase", task_id=task_id, error=str(e), exc_info=True); return ("error", None)

def setup_logging(log_level_str: str):
    """
    Configures the world-class logging system.
    ✅ FIX: Removed redundant 'format_exc_info' processor to prevent duplicate exception logging.
    """
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            # ✅ CRITICAL FIX: This redundant processor, which caused duplicate logs, is removed.
            # structlog.processors.format_exc_info, 
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )
    
    handler = RichHandler(level=log_level, rich_tracebacks=True)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    # Clear any existing handlers to prevent duplicates in some environments (e.g., notebooks)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("django").setLevel(logging.WARNING)
    
    logger.info("Logging system configured", log_level=log_level_str, renderer="RichConsole")

async def main_loop():
    try:
        with open('config.json', 'r', encoding='utf-8') as f: config = json.load(f)
    except Exception as e: print(f"FATAL: Could not load or parse 'config.json'. Error: {e}"); return

    general_config = config.get("general", {}); log_level_str = general_config.get("log_level", "INFO"); setup_logging(log_level_str)
    symbols, timeframes = general_config.get("symbols_to_monitor", []), general_config.get("timeframes_to_analyze", [])
    poll_interval, max_concurrent = general_config.get("poll_interval_seconds", 300), general_config.get("max_concurrent_tasks", 5)

    fetcher, orchestrator, telegram, cache = ExchangeFetcher(config.get("exchange_settings", {})), MasterOrchestrator(config), TelegramHandler(), SignalCache(config.get("signal_cache", {}).get("ttl_map_hours", {}), config.get("signal_cache", {}).get("default_ttl_hours", 4))
    version, analysis_state = orchestrator.ENGINE_VERSION, {}
    await telegram.send_message_async(f"✅ *AiSignalPro Bot (v{version}) is LIVE!* (Log Level: {log_level_str})")
    
    semaphore, cycle_count = asyncio.Semaphore(max_concurrent), 0
    while True:
        cycle_count += 1; start_time = time.time()
        
        start_message = (
            f"═══════════════════ 🔄 Cycle Started ═══════════════════\n"
            f" Cycle ID: {cycle_count} | Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
            f" Symbols: {symbols}\n"
            f" Timeframes: {timeframes}\n"
            f" Settings: Max Concurrent={max_concurrent}, Poll Interval={poll_interval}s"
        )
        logger.info(start_message)
        
        global_context, new_states = {s: {} for s in symbols}, {}
        
        logger.debug("Creating analysis tasks..."); analysis_tasks = [run_single_analysis(s, tf, orchestrator, fetcher, analysis_state, global_context, new_states, semaphore) for s in symbols for tf in timeframes]
        analysis_results = await asyncio.gather(*analysis_tasks); analysis_state.update(new_states)
        analysis_stats = Counter(result[0] for result in analysis_results)
        logger.info("[Phase 1/2] Analysis", success=analysis_stats['success'], warnings=analysis_stats['warning'], errors=analysis_stats['error'], total=len(analysis_results))

        logger.debug("Creating strategy tasks..."); strategy_tasks = [run_single_strategy(s, tf, orchestrator, global_context, cache, telegram, semaphore) for s in symbols for tf in timeframes]
        strategy_results = await asyncio.gather(*strategy_tasks)
        strategy_stats = Counter(result[0] for result in strategy_results)
        logger.info("[Phase 2/2] Strategy", signals_sent=strategy_stats['signal_sent'], send_failures=strategy_stats['send_failed'], no_signal=strategy_stats['no_signal'], errors=strategy_stats['error'])
        
        cycle_duration = time.time() - start_time
        
        end_message = (
            f"═══════════════════ ✅ Cycle Completed ════════════════════\n"
            f" Cycle ID: {cycle_count} | Duration: {cycle_duration:.2f}s\n"
            f" Analysis Summary: {analysis_stats['success']} success, {analysis_stats['warning']} warning, {analysis_stats['error']} error\n"
            f" Strategy Summary: {strategy_stats['signal_sent']} signals generated\n"
            f" > Sleeping {poll_interval}s before next cycle..."
        )
        logger.info(end_message)
        
        await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    try: asyncio.run(main_loop())
    except KeyboardInterrupt: logger.info("Bot stopped by user.")
    except Exception as e: logger.critical("A fatal error occurred in the main runner", error=str(e), exc_info=True)
