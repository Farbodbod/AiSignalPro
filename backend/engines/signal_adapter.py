# engines/signal_adapter.py (نسخه 2.1 - اصلاح پیام AI)

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
import pytz
from jdatetime import datetime as jdatetime

logger = logging.getLogger(__name__)

class SignalAdapter:
    def __init__(self, signal_package: Dict[str, Any]):
        self.package = signal_package
        self.signal = signal_package.get("base_signal", {})
        self.ai_confirmation = signal_package.get("ai_confirmation", {})
        self.symbol = signal_package.get("symbol", "N/A")
        self.timeframe = signal_package.get("timeframe", "N/A")
        self.full_analysis = signal_package.get("full_analysis", {})

    def _get_system_confidence(self) -> float:
        # ... (کد این متد از پاسخ قبلی کامل است)
        priority_map = {"SuperSignal Confluence": 99.0, "DivergenceSniper": 95.0, "VolumeCatalyst": 90.0, "IchimokuPro": 88.0, "TrendRider": 85.0, "PivotReversalStrategy": 82.0, "MeanReversionStrategy": 78.0}
        strategy_name = self.signal.get('strategy_name', '')
        if strategy_name == 'MeanReversionPro': return 78.0
        return priority_map.get(strategy_name, 75.0)

    def _get_valid_until(self) -> str:
        # ... (کد این متد از پاسخ قبلی کامل است)
        ttl_map = {'15m': 4, '1h': 8, '4h': 24, '1d': 72}; hours_to_add = ttl_map.get(self.timeframe, 4); valid_until_utc = datetime.utcnow() + timedelta(hours=hours_to_add); tehran_tz = pytz.timezone("Asia/Tehran"); tehran_dt = valid_until_utc.astimezone(tehran_tz); jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt); return f"⏳ Valid Until: {jalali_dt.strftime('%Y/%m/%d, %H:%M')}"

    def _get_signal_summary(self) -> str:
        # ... (کد این متد از پاسخ قبلی کامل است)
        direction = self.signal.get('direction', 'HOLD'); strategy = self.signal.get('strategy_name', '')
        if "Divergence" in strategy or "Reversion" in strategy or "Sniper" in strategy: return f"High-Probability {direction} Reversal Signal"
        elif "Trend" in strategy or "Breakout" in strategy or "Catalyst" in strategy or "Ichimoku" in strategy: return f"Strong {direction} Continuation Signal"
        elif "Confluence" in strategy: return f"MAXIMUM CONVICTION {direction} SIGNAL"
        return f"System Signal: {direction}"

    def _get_signal_emoji_and_text(self) -> (str, str):
        direction = self.signal.get('direction', 'HOLD');
        if direction == 'BUY': return "🟢", "LONG"
        elif direction == 'SELL': return "🔴", "SHORT"
        return "⚪️", "NEUTRAL"

    def _format_targets(self) -> str:
        targets = self.signal.get('targets', []);
        if not targets: return "  (Calculated based on R/R)"
        return "\n".join([f"    🎯 TP{i+1}: `{t:,.4f}`" for i, t in enumerate(targets)])

    def _get_timestamp(self) -> str:
        try:
            utc_dt = datetime.utcnow(); tehran_tz = pytz.timezone("Asia/Tehran"); tehran_dt = utc_dt.astimezone(tehran_tz); jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt); return f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
        except Exception: return ""

    def to_telegram_message(self) -> str:
        emoji, direction_text = self._get_signal_emoji_and_text()
        strategy_name = self.signal.get('strategy_name', 'N/A')
        entry_price = self.signal.get('entry_price', 0.0)
        stop_loss = self.signal.get('stop_loss', 0.0)
        rr_ratio = self.signal.get('risk_reward_ratio', 0.0)
        
        system_confidence = self._get_system_confidence()
        valid_until_str = self._get_valid_until()
        signal_summary = self._get_signal_summary()
        
        # --- ✨ تغییر کلیدی: استفاده از پیام صحیح برای Cooldown ---
        ai_explanation = self.ai_confirmation.get('explanation_fa', "AI analysis was not performed.")

        key_levels = self.full_analysis.get("structure", {}).get("key_levels", {})
        supports = key_levels.get('supports', []); resistances = key_levels.get('resistances', [])
        supports_str = "\n".join([f"    - `{s:,.4f}`" for s in supports[:5]]) if supports else "Not Available"
        resistances_str = "\n".join([f"    - `{r:,.4f}`" for r in resistances[:5]]) if resistances else "Not Available"

        return (
            f"🔥 **AiSignalPro - Signal v2.0** 🔥\n\n"
            f"🪙 **{self.symbol}** | `{self.timeframe}`\n"
            f"📊 Signal: *{emoji} {direction_text}*\n"
            f"♟️ Strategy: _{strategy_name}_\n\n"
            f"🎯 **System Confidence: {system_confidence:.1f}%**\n"
            f"🧠 **AI Confidence: {self.ai_confirmation.get('confidence', 0):.1f}%**\n"
            f"📊 R/R (to TP1): `1:{rr_ratio:.2f}`\n"
            f"----------------------------------------\n"
            f"📈 **Entry Price:** `{entry_price:,.4f}`\n"
            f"🛑 **Stop Loss:** `{stop_loss:,.4f}`\n\n"
            f"🎯 **Targets (Structure-Based):**\n{self._format_targets()}\n"
            f"----------------------------------------\n"
            f"📈 **Support Levels:**\n{supports_str}\n\n"
            f"🛡️ **Resistance Levels:**\n{resistances_str}\n"
            f"----------------------------------------\n"
            f"💡 **Signal Conclusion:**\n_{signal_summary}_\n\n"
            f"🤖 **AI Analysis:**\n_{ai_explanation}_\n\n"
            f"⚠️ *Risk Management: Use 2-3% of your capital.*\n"
            f"{self._get_timestamp()}\n"
            f"{valid_until_str}"
        )
