# live_monitor_worker.py (نسخه کاملاً نهایی 3.1)

import asyncio, os, django, logging, time
from typing import Dict, Optional
from datetime import datetime
import pytz
from jdatetime import datetime as jdatetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator, EngineConfig
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

SYMBOLS_TO_MONITOR = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']
TIME_FRAMES_TO_ANALYZE = ['5m', '15m', '1h', '4h']
POLL_INTERVAL_SECONDS = 900
SIGNAL_CACHE_TTL_SECONDS = 3600

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')
logger = logging.getLogger(__name__)

class SignalCache:
    def __init__(self, ttl_seconds: int): self.cache: Dict[str, tuple] = {}; self.ttl = ttl_seconds
    def is_duplicate(self, symbol: str, signal_type: str) -> bool:
        now = time.time()
        if symbol in self.cache:
            last_signal, last_time = self.cache[symbol]
            if signal_type == last_signal and (now - last_time) < self.ttl: return True
        return False
    def store(self, symbol: str, signal_type: str): self.cache[symbol] = (signal_type, time.time())

def format_legendary_message(signal_obj: dict) -> str:
    symbol, timeframe, signal_type, strategy_name = (signal_obj.get(k, "N/A") for k in ["symbol", "timeframe", "signal_type", "strategy_name"])
    winning_strategy = signal_obj.get("winning_strategy", {})
    entry_zone, stop_loss, targets, rr_ratio = (winning_strategy.get(k) for k in ["entry_zone", "stop_loss", "targets", "risk_reward_ratio"])
    
    analysis_details = signal_obj.get("full_analysis_details", {}).get(timeframe, {})
    key_levels = analysis_details.get("market_structure", {}).get("key_levels", {})
    supports, resistances = key_levels.get('supports', []), key_levels.get('resistances', [])
    
    sys_confidence, ai_confidence, ai_explanation = (signal_obj.get(k, 0) for k in ["system_confidence_percent", "ai_confidence_percent", "explanation_fa"])
    if not isinstance(ai_explanation, str) or ai_explanation == "N/A": ai_explanation = "AI analysis skipped due to cooldown."
    
    confirmations = winning_strategy.get("confirmations", [])
    issued_at_utc_str, valid_until_utc_str = signal_obj.get("issued_at", ""), signal_obj.get("valid_until", "")
    
    signal_header = "🟢 LONG (BUY)" if signal_type == "BUY" else "🔴 SHORT (SELL)"
    entry_range_str = f"`{entry_zone[0]:.4f} - {entry_zone[1]:.4f}`" if entry_zone and len(entry_zone) > 1 else "N/A"
    targets_str = "\n".join([f"    🎯 TP{i+1}: `{t:.4f}`" for i, t in enumerate(targets)]) if targets else ""
    rr_str = f"📊 R/R (to TP1): `1:{rr_ratio:.2f}`" if rr_ratio else ""
    
    supports_str = "\n".join([f"    - `{s:.4f}`" for s in supports]) if supports else "Not Available"
    resistances_str = "\n".join([f"    - `{r:.4f}`" for r in resistances]) if resistances else "Not Available"
    
    tehran_tz = pytz.timezone("Asia/Tehran")
    try:
        utc_dt = datetime.fromisoformat(issued_at_utc_str.replace('Z', '+00:00'))
        jalali_dt = jdatetime.fromgregorian(datetime=utc_dt.astimezone(tehran_tz))
        timestamp_str = f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
    except Exception: timestamp_str = ""

    valid_until_str = ""
    if valid_until_utc_str:
        try:
            utc_valid_dt = datetime.fromisoformat(valid_until_utc_str.replace('Z', '+00:00'))
            jalali_valid_dt = jdatetime.fromgregorian(datetime=utc_valid_dt.astimezone(tehran_tz))
            valid_until_str = f"⏳ Valid Until: {jalali_valid_dt.strftime('%H:%M')}"
        except Exception: pass

    explanation_section = ""
    if "skipped" not in ai_explanation:
        explanation_section = f"🤖 **AI Analysis:**\n_{ai_explanation}_"
    elif confirmations:
        explanation_section = f"⚙️ **System Reasons:**\n_{', '.join(confirmations)}_"

    return (
        f"🔥 **AiSignalPro - NEW SIGNAL** 🔥\n\n"
        f"🪙 **{symbol}/USDT** | `{timeframe}`\n"
        f"📊 Signal: *{signal_header}*\n"
        f"♟️ Strategy: _{strategy_name}_\n\n"
        f"🎯 System Confidence: *{sys_confidence:.1f}%* | 🧠 AI Score: *{ai_confidence:.1f}%*\n"
        f"{rr_str}\n"
        f"----------------------------------------\n"
        f"📈 **Entry Zone:**\n"
        f"    {entry_range_str}\n\n"
        f"🎯 **Targets:**\n{targets_str}\n\n"
        f"🛑 **Stop Loss:**\n"
        f"    `{stop_loss:.4f}`\n"
        f"----------------------------------------\n"
        f"🛡️ **Key Resistance Levels:**\n{resistances_str}\n\n"
        f"📈 **Key Support Levels:**\n{supports_str}\n\n"
        f"{explanation_section}\n\n"
        f"⚠️ *Risk Management: Use 2-3% of your capital.*\n"
        f"{timestamp_str}\n"
        f"{valid_until_str}"
    )

async def analyze_symbol(fetcher: ExchangeFetcher, orchestrator: MasterOrchestrator, symbol: str) -> Optional[dict]:
    dataframes = {}
    tasks = [fetcher.get_first_successful_klines(symbol, tf) for tf in TIME_FRAMES_TO_ANALYZE]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, res in enumerate(results):
        tf = TIME_FRAMES_TO_ANALYZE[i]
        if isinstance(res, Exception) or not (res and res[0] is not None): continue
        df, source = res; dataframes[tf] = df
    if not dataframes: return None
    final_result = await orchestrator.get_final_signal(dataframes, symbol)
    adapter = SignalAdapter(final_result)
    signal_object = adapter.generate_final_signal()
    if signal_object:
        signal_object['full_analysis_details'] = final_result.get('full_analysis_details', {})
        signal_object['winning_strategy'] = final_result.get('winning_strategy', {})
    return signal_object

async def monitor_loop():
    engine_config = EngineConfig()
    orchestrator = MasterOrchestrator(config=engine_config)
    telegram = TelegramHandler(); signal_cache = SignalCache(SIGNAL_CACHE_TTL_SECONDS); fetcher = ExchangeFetcher()
    logger.info("Live Monitoring Worker (v3.1 - Final Audit) started.")
    try: await telegram.send_message_async("✅ *ربات AiSignalPro (نسخه نهایی بازبینی شده) فعال شد.*")
    except Exception as e: logger.error(f"Failed to send initial Telegram message: {e}")
    while True:
        try:
            logger.info("--- Starting New Monitoring Cycle ---")
            for symbol in SYMBOLS_TO_MONITOR:
                signal_obj = await analyze_symbol(fetcher, orchestrator, symbol)
                if signal_obj:
                    if not signal_cache.is_duplicate(symbol, signal_obj["signal_type"]):
                        signal_cache.store(symbol, signal_obj["signal_type"])
                        await telegram.send_message_async(format_legendary_message(signal_obj))
                        logger.info(f"LEGENDARY ALERT SENT for {symbol}: {signal_obj['signal_type']}")
                    else: logger.info(f"Duplicate signal for {symbol}. Skipping.")
                else: logger.info(f"No actionable signal for {symbol}.")
                await asyncio.sleep(10)
            logger.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds.")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.critical(f"Critical error in main loop: {e}", exc_info=True)
            await asyncio.sleep(60)

if __name__ == "__main__":
    try: asyncio.run(monitor_loop())
    except KeyboardInterrupt: logger.info("Monitoring worker stopped by user.")
