# live_monitor_worker.py (با نمایش تحلیل فارسی)

import asyncio
import os
import django
import logging
import time
from typing import Dict, Optional
from datetime import datetime
import pytz
from jdatetime import datetime as jdatetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

SYMBOLS_TO_MONITOR = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']
TIME_FRAMES_TO_ANALYZE = ['5m', '15m', '1h', '4h']
POLL_INTERVAL_SECONDS = 900
SIGNAL_CACHE_TTL_SECONDS = 3600
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')

class SignalCache:
    def __init__(self, ttl_seconds: int): self.cache = {}; self.ttl = ttl_seconds
    def is_duplicate(self, symbol: str, signal_type: str) -> bool:
        now = time.time();
        if symbol in self.cache:
            last_signal, last_time = self.cache[symbol];
            if signal_type == last_signal and (now - last_time) < self.ttl: return True
        return False
    def store(self, symbol: str, signal_type: str): self.cache[symbol] = (signal_type, time.time())

def format_legendary_message(signal_obj: dict) -> str:
    signal_type = signal_obj.get("signal_type", "N/A"); symbol = signal_obj.get("symbol", "N/A"); timeframe = signal_obj.get("timeframe", "N/A"); entry_zone = signal_obj.get("entry_zone", []); stop_loss = signal_obj.get("stop_loss", 0.0); targets = signal_obj.get("targets", []); sys_confidence = signal_obj.get("system_confidence_percent", 0); ai_confidence = signal_obj.get("ai_confidence_percent", 0); 
    explanation = signal_obj.get("explanation_fa", "تحلیل AI ارائه نشد.")
    issued_at_utc_str = signal_obj.get("issued_at", datetime.utcnow().isoformat());
    signal_header = "🟢 LONG" if signal_type == "BUY" else "🔴 SHORT"; entry_range_str = f"`{entry_zone[0]:,.4f} - {entry_zone[1]:,.4f}`" if len(entry_zone) > 1 else (f"`{entry_zone[0]:,.4f}`" if entry_zone else "N/A"); targets_str = "\n".join([f"    🎯 TP{i+1}: `{t:,.4f}`" for i, t in enumerate(targets)]);
    try:
        utc_dt = datetime.fromisoformat(issued_at_utc_str.replace('Z', '+00:00')); tehran_tz = pytz.timezone("Asia/Tehran"); tehran_dt = utc_dt.astimezone(tehran_tz); jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt); timestamp_str = f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
    except Exception: timestamp_str = ""
    message = (
        f"🔥 **NEW AI SIGNAL** 🔥\n\n"
        f"🪙 **{symbol}/USDT** | `{timeframe}`\n"
        f"📊 Signal: *{signal_header}*\n\n"
        f"🎯 Confidence: *{sys_confidence:.1f}%* | 🧠 AI Score: *{ai_confidence:.1f}%*\n"
        f"----------------------------------------\n"
        f"📈 **Entry Range:**\n"
        f"    {entry_range_str}\n\n"
        f"🎯 **Targets:**\n{targets_str}\n\n"
        f"🛑 **Stop Loss:**\n"
        f"    `{stop_loss:,.4f}`\n"
        f"----------------------------------------\n"
        f"🤖 **AI Analysis:**\n"
        f"_{explanation}_\n\n"
        f"⚠️ *Risk Management: Use 2-3% of your capital.*\n"
        f"{timestamp_str}"
    )
    return message

async def analyze_symbol(fetcher: ExchangeFetcher, orchestrator: MasterOrchestrator, symbol: str) -> Optional[dict]:
    all_tf_analysis = {};
    tasks = [fetcher.get_first_successful_klines(symbol, tf) for tf in TIME_FRAMES_TO_ANALYZE]
    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        if result and result[0] is not None:
            df, source = result; tf = TIME_FRAMES_TO_ANALYZE[i]; analysis = orchestrator.analyze_single_dataframe(df, tf, symbol); analysis['source'] = source; all_tf_analysis[tf] = analysis
    if not all_tf_analysis:
        logging.warning(f"Could not fetch any kline data for {symbol} to perform analysis."); return None
    final_result = await orchestrator.get_multi_timeframe_signal(all_tf_analysis)
    adapter = SignalAdapter(analytics_output=final_result)
    return adapter.combine()

async def monitor_loop():
    telegram = TelegramHandler(); orchestrator = MasterOrchestrator(); signal_cache = SignalCache(SIGNAL_CACHE_TTL_SECONDS); fetcher = ExchangeFetcher(); logging.info("Live Monitoring Worker (Final Stable Edition) started successfully.");
    try: await telegram.send_message_async("✅ *ربات مانیتورینگ AiSignalPro (نسخه نهایی پایدار) فعال شد.*")
    except Exception as e: logging.error(f"Failed to send initial Telegram message: {e}")
    try:
        while True:
            logging.info("--- Starting New Monitoring Cycle ---");
            for symbol in SYMBOLS_TO_MONITOR:
                try:
                    logging.info(f"Analyzing {symbol}..."); signal_obj = await analyze_symbol(fetcher, orchestrator, symbol)
                    if signal_obj and signal_obj.get("signal_type") != "HOLD":
                        signal_type = signal_obj["signal_type"];
                        if not signal_cache.is_duplicate(symbol, signal_type):
                            signal_cache.store(symbol, signal_type); message = format_legendary_message(signal_obj); await telegram.send_message_async(message); logging.info(f"LEGENDARY ALERT SENT for {symbol}: {signal_type}")
                        else: logging.info(f"Duplicate signal '{signal_type}' for {symbol}. Skipping.")
                    await asyncio.sleep(5)
                except Exception as e: logging.error(f"An exception occurred during analysis for {symbol}: {e}", exc_info=True)
            logging.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds."); await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally: await fetcher.close()

if __name__ == "__main__":
    try: asyncio.run(monitor_loop())
    except KeyboardInterrupt: logging.info("Monitoring worker stopped by user.")
