# live_monitor_worker.py (نسخه نهایی 3.0 - با پیام‌های کامل و حرفه‌ای)

import asyncio, os, django, logging, time
from typing import Dict, Optional, List
from datetime import datetime
import pytz
from jdatetime import datetime as jdatetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator, EngineConfig
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

# ... (بخش ثابت‌ها و کلاس SignalCache بدون تغییر باقی می‌ماند) ...
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

# --- ✨ تابع فرمت پیام کاملاً بازنویسی و هوشمند شده ✨ ---
def format_legendary_message(signal_obj: dict) -> str:
    # استخراج تمام داده‌های لازم
    signal_type = signal_obj.get("signal_type", "N/A")
    symbol = signal_obj.get("symbol", "N/A")
    timeframe = signal_obj.get("timeframe", "N/A")
    strategy_name = signal_obj.get("strategy_name", "Unknown")
    # جدید: استخراج دلایل سیستم از آبجکت استراتژی برنده
    winning_strategy = signal_obj.get("winning_strategy", {})
    confirmations = winning_strategy.get("confirmations", [])
    
    entry_zone = signal_obj.get("entry_zone", [])
    stop_loss = signal_obj.get("stop_loss", 0.0)
    targets = signal_obj.get("targets", [])
    
    sys_confidence = signal_obj.get("system_confidence_percent", 0)
    ai_confidence = signal_obj.get("ai_confidence_percent", 0)
    ai_explanation = signal_obj.get("explanation_fa", "AI analysis skipped due to cooldown.")
    
    issued_at_utc_str = signal_obj.get("issued_at", datetime.utcnow().isoformat())
    valid_until_utc_str = signal_obj.get("valid_until", "") # <-- جدید

    # آماده‌سازی بخش‌های مختلف پیام
    signal_header = "🟢 LONG (BUY)" if signal_type == "BUY" else "🔴 SHORT (SELL)"
    entry_range_str = f"`{entry_zone[0]:.4f} - {entry_zone[1]:.4f}`" if len(entry_zone) > 1 else f"`{entry_zone[0]:.4f}`"
    targets_str = "\n".join([f"    🎯 TP{i+1}: `{t:.4f}`" for i, t in enumerate(targets)])
    
    tehran_tz = pytz.timezone("Asia/Tehran")
    try:
        utc_dt = datetime.fromisoformat(issued_at_utc_str.replace('Z', '+00:00'))
        tehran_dt = utc_dt.astimezone(tehran_tz)
        jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
        timestamp_str = f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
    except Exception:
        timestamp_str = ""

    # جدید: فرمت کردن زمان اعتبار سیگنال
    valid_until_str = ""
    if valid_until_utc_str:
        try:
            utc_valid_dt = datetime.fromisoformat(valid_until_utc_str.replace('Z', '+00:00'))
            tehran_valid_dt = utc_valid_dt.astimezone(tehran_tz)
            jalali_valid_dt = jdatetime.fromgregorian(datetime=tehran_valid_dt)
            valid_until_str = f"⏳ Valid Until: {jalali_valid_dt.strftime('%H:%M')}"
        except Exception:
            pass

    # جدید: ساختن بخش توضیحات هوشمند
    explanation_section = ""
    if "skipped due to cooldown" not in ai_explanation:
        explanation_section = f"🤖 **AI Analysis:**\n_{ai_explanation}_"
    elif confirmations:
        confirmations_str = ", ".join(confirmations)
        explanation_section = f"⚙️ **System Reasons:**\n_{confirmations_str}_"

    return (
        f"🔥 **AiSignalPro - NEW SIGNAL** 🔥\n\n"
        f"🪙 **{symbol}/USDT** | `{timeframe}`\n"
        f"📊 Signal: *{signal_header}*\n"
        f"♟️ Strategy: _{strategy_name}_\n\n"
        f"🎯 System Confidence: *{sys_confidence:.1f}%* | 🧠 AI Score: *{ai_confidence:.1f}%*\n"
        f"----------------------------------------\n"
        f"📈 **Entry Zone:**\n"
        f"    {entry_range_str}\n\n"
        f"🎯 **Targets:**\n{targets_str}\n\n"
        f"🛑 **Stop Loss:**\n"
        f"    `{stop_loss:.4f}`\n"
        f"----------------------------------------\n"
        f"{explanation_section}\n\n"
        f"⚠️ *Risk Management: Use 2-3% of your capital.*\n"
        f"{timestamp_str}\n"
        f"{valid_until_str}"
    )

# ... (تابع analyze_symbol و حلقه اصلی monitor_loop بدون تغییر باقی می‌مانند) ...
async def analyze_symbol(fetcher: ExchangeFetcher, orchestrator: MasterOrchestrator, symbol: str) -> Optional[dict]:
    logger.info(f"Gathering data for {symbol}...")
    dataframes = {}
    tasks = [fetcher.get_first_successful_klines(symbol, tf) for tf in TIME_FRAMES_TO_ANALYZE]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, res in enumerate(results):
        tf = TIME_FRAMES_TO_ANALYZE[i]
        if isinstance(res, Exception) or not (res and res[0] is not None): continue
        df, source = res; dataframes[tf] = df
    if not dataframes:
        logger.error(f"Could not fetch any valid kline data for {symbol}."); return None
    logger.info(f"Analyzing collected data for {symbol}...")
    final_result = await orchestrator.get_final_signal(dataframes, symbol)
    
    # جدید: آبجکت استراتژی برنده را به آبجکت سیگنال نهایی اضافه می‌کنیم
    adapter = SignalAdapter(final_result)
    signal_object = adapter.generate_final_signal()
    if signal_object:
        signal_object['winning_strategy'] = final_result.get('winning_strategy', {})
    return signal_object

async def monitor_loop():
    engine_config = EngineConfig()
    orchestrator = MasterOrchestrator(config=engine_config)
    telegram = TelegramHandler(); signal_cache = SignalCache(SIGNAL_CACHE_TTL_SECONDS); fetcher = ExchangeFetcher()
    logger.info("Live Monitoring Worker (v3.0 - Full Featured Messaging) started.")
    try: await telegram.send_message_async("✅ *ربات AiSignalPro (نسخه نهایی با پیام‌های کامل) فعال شد.*")
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
