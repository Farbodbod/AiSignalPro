# live_monitor_worker.py (نسخه کاملاً نهایی و بی‌نقص 3.3)

import asyncio
import os
import django
import logging
import time
from typing import Dict, Optional
from datetime import datetime
import pytz
from jdatetime import datetime as jdatetime

# --- تنظیمات اولیه جنگو ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

# --- وارد کردن ماژول‌های پروژه ---
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.config import EngineConfig
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

# --- تعریف ثابت‌های مانیتورینگ ---
SYMBOLS_TO_MONITOR = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']
TIME_FRAMES_TO_ANALYZE = ['5m', '15m', '1h', '4h']
POLL_INTERVAL_SECONDS = 900  # 15 دقیقه
SIGNAL_CACHE_TTL_SECONDS = 3600 # 1 ساعت

# --- تنظیمات لاگینگ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- کلاس داخلی برای مدیریت سیگنال‌های تکراری ---
class SignalCache:
    """کلاسی برای جلوگیری از ارسال سیگنال‌های تکراری در یک بازه زمانی مشخص."""
    def __init__(self, ttl_seconds: int):
        self.cache: Dict[str, tuple] = {}
        self.ttl = ttl_seconds

    def is_duplicate(self, symbol: str, signal_type: str) -> bool:
        """بررسی می‌کند که آیا سیگنال برای یک نماد تکراری است یا خیر."""
        now = time.time()
        if symbol in self.cache:
            last_signal, last_time = self.cache[symbol]
            if signal_type == last_signal and (now - last_time) < self.ttl:
                return True
        return False

    def store(self, symbol: str, signal_type: str):
        """سیگنال جدید را در حافظه کش ذخیره می‌کند."""
        self.cache[symbol] = (signal_type, time.time())

# --- تابع فرمت‌بندی پیام تلگرام (کامل و نهایی) ---
def format_legendary_message(signal_obj: dict) -> str:
    """یک آبجکت سیگنال نهایی را به یک پیام تلگرام کامل و خوانا تبدیل می‌کند."""
    # --- استخراج داده‌ها ---
    symbol = signal_obj.get("symbol", "N/A")
    timeframe = signal_obj.get("timeframe", "N/A")
    signal_type = signal_obj.get("signal_type", "N/A")
    strategy_name = signal_obj.get("strategy_name", "Unknown")
    
    winning_strategy = signal_obj.get("winning_strategy", {})
    entry_zone = winning_strategy.get("entry_zone", [])
    stop_loss = winning_strategy.get("stop_loss", 0.0)
    targets = winning_strategy.get("targets", [])
    rr_ratio = winning_strategy.get("risk_reward_ratio")
    confirmations = winning_strategy.get("confirmations", [])
    
    analysis_details = signal_obj.get("full_analysis_details", {}).get(timeframe, {})
    key_levels = analysis_details.get("market_structure", {}).get("key_levels", {})
    supports = key_levels.get('supports', [])
    resistances = key_levels.get('resistances', [])
    
    sys_confidence = signal_obj.get("system_confidence_percent", 0)
    ai_confidence = signal_obj.get("ai_confidence_percent", 0)
    ai_explanation = signal_obj.get("explanation_fa", "AI analysis skipped due to cooldown.")
    if not isinstance(ai_explanation, str) or ai_explanation == "N/A":
        ai_explanation = "AI analysis skipped due to cooldown."
    
    issued_at_utc_str = signal_obj.get("issued_at", "")
    valid_until_utc_str = signal_obj.get("valid_until", "")

    # --- فرمت‌بندی بخش‌های پیام ---
    signal_header = "🟢 LONG (BUY)" if signal_type == "BUY" else "🔴 SHORT (SELL)"
    entry_range_str = f"`{entry_zone[0]:.4f} - {entry_zone[1]:.4f}`" if entry_zone and len(entry_zone) > 1 else "N/A"
    targets_str = "\n".join([f"    🎯 TP{i+1}: `{t:.4f}`" for i, t in enumerate(targets)]) if targets else ""
    rr_str = f"📊 R/R (to TP1): `1:{rr_ratio:.2f}`" if rr_ratio else ""
    supports_str = "\n".join([f"    - `{s:.4f}`" for s in supports]) if supports else "Not Available"
    resistances_str = "\n".join([f"    - `{r:.4f}`" for r in resistances]) if resistances else "Not Available"
    
    tehran_tz = pytz.timezone("Asia/Tehran")
    timestamp_str = ""
    if issued_at_utc_str:
        try:
            utc_dt = datetime.fromisoformat(issued_at_utc_str.replace('Z', '+00:00'))
            jalali_dt = jdatetime.fromgregorian(datetime=utc_dt.astimezone(tehran_tz))
            timestamp_str = f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
        except Exception: pass

    valid_until_str = ""
    if valid_until_utc_str:
        try:
            utc_valid_dt = datetime.fromisoformat(valid_until_utc_str.replace('Z', '+00:00'))
            jalali_valid_dt = jdatetime.fromgregorian(datetime=utc_valid_dt.astimezone(tehran_tz))
            valid_until_str = f"⏳ Valid Until: {jalali_valid_dt.strftime('%Y/%m/%d, %H:%M')}"
        except Exception: pass

    explanation_section = ""
    if "skipped" not in ai_explanation:
        explanation_section = f"🤖 **AI Analysis:**\n_{ai_explanation}_"
    elif confirmations:
        explanation_section = f"⚙️ **System Reasons:**\n_{', '.join(confirmations)}_"

    # --- ساختار نهایی پیام ---
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

# --- توابع اصلی برای تحلیل و مانیتورینگ ---
async def analyze_symbol(fetcher: ExchangeFetcher, orchestrator: MasterOrchestrator, symbol: str) -> Optional[dict]:
    """خط لوله کامل تحلیل برای یک نماد خاص."""
    logger.info(f"Gathering data for {symbol}...")
    dataframes = {}
    tasks = [fetcher.get_first_successful_klines(symbol, tf) for tf in TIME_FRAMES_TO_ANALYZE]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, res in enumerate(results):
        tf = TIME_FRAMES_TO_ANALYZE[i]
        if isinstance(res, Exception) or not (res and res[0] is not None):
            logger.warning(f"Could not fetch data for {symbol}@{tf}. Reason: {res}")
            continue
        df, source = res
        dataframes[tf] = df
        
    if not dataframes:
        logger.error(f"Could not fetch any valid kline data for {symbol}.")
        return None
        
    logger.info(f"Analyzing collected data for {symbol}...")
    final_result = await orchestrator.get_final_signal(dataframes, symbol)
    
    adapter = SignalAdapter(final_result)
    signal_object = adapter.generate_final_signal()
    if signal_object:
        signal_object['full_analysis_details'] = final_result.get('full_analysis_details', {})
        signal_object['winning_strategy'] = final_result.get('winning_strategy', {})
    return signal_object

async def monitor_loop():
    """حلقه اصلی مانیتورینگ که به صورت ۲۴/۷ اجرا می‌شود."""
    engine_config = EngineConfig()
    orchestrator = MasterOrchestrator(config=engine_config)
    telegram = TelegramHandler()
    signal_cache = SignalCache(SIGNAL_CACHE_TTL_SECONDS)
    fetcher = ExchangeFetcher()
    
    logger.info("Live Monitoring Worker (v3.3 - Flawless Edition) started.")
    try:
        await telegram.send_message_async("✅ *ربات AiSignalPro (نسخه نهایی و بی‌نقص) با موفقیت فعال شد.*")
    except Exception as e:
        logger.error(f"Failed to send initial Telegram message: {e}")
    
    while True:
        try:
            logger.info("--- Starting New Monitoring Cycle ---")
            for symbol in SYMBOLS_TO_MONITOR:
                signal_obj = await analyze_symbol(fetcher, orchestrator, symbol)
                if signal_obj:
                    if not signal_cache.is_duplicate(symbol, signal_obj["signal_type"]):
                        signal_cache.store(symbol, signal_obj["signal_type"])
                        message = format_legendary_message(signal_obj)
                        await telegram.send_message_async(message)
                        logger.info(f"LEGENDARY ALERT SENT for {symbol}: {signal_obj['signal_type']}")
                    else:
                        logger.info(f"Duplicate signal for {symbol}. Skipping.")
                else:
                    logger.info(f"No actionable signal for {symbol}.")
                await asyncio.sleep(10)
            
            logger.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds.")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.critical(f"A critical error occurred in the main monitoring loop: {e}", exc_info=True)
            await asyncio.sleep(60)

# --- نقطه شروع اجرای اسکریپت ---
if __name__ == "__main__":
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        logger.info("Monitoring worker stopped by user.")
    finally:
        logger.info("Monitoring worker shut down.")
