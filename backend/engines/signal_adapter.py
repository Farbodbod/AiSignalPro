# engines/signal_adapter.py (نسخه جدید برای معماری ماژولار)

import logging
from typing import Dict, Any
from datetime import datetime
import pytz
from jdatetime import datetime as jdatetime

logger = logging.getLogger(__name__)

class SignalAdapter:
    """
    این کلاس یک سیگنال خام تولید شده توسط یک استراتژی را دریافت کرده
    و آن را به فرمت‌های مختلف خروجی (مانند پیام تلگرام) تبدیل می‌کند.
    """
    def __init__(self, strategy_signal: Dict[str, Any], symbol: str, timeframe: str):
        self.signal = strategy_signal
        self.symbol = symbol
        self.timeframe = timeframe
        self.ai_confirmation = {} # این فیلد بعداً توسط MasterOrchestrator پر می‌شود

    def set_ai_confirmation(self, ai_data: Dict[str, Any]):
        """برای افزودن تحلیل Gemini به سیگنال."""
        self.ai_confirmation = ai_data

    def _get_signal_emoji_and_text(self) -> (str, str):
        direction = self.signal.get('direction', 'HOLD')
        if direction == 'BUY':
            return "🟢", "LONG"
        elif direction == 'SELL':
            return "🔴", "SHORT"
        return "⚪️", "NEUTRAL"

    def _format_targets(self) -> str:
        targets = self.signal.get('targets', [])
        if not targets: return "N/A"
        return "\n".join([f"    🎯 TP{i+1}: `{t:,.4f}`" for i, t in enumerate(targets)])

    def _format_confirmations(self) -> str:
        confirmations = self.signal.get('confirmations', {})
        if not confirmations: return "• _Based on strategy rules._"
        
        lines = []
        for key, value in confirmations.items():
            # فرمت‌بندی کلید برای خوانایی (مثال: adx_strength -> ADX Strength)
            formatted_key = key.replace('_', ' ').title()
            lines.append(f"• _{formatted_key}:_ {value}")
        return "\n".join(lines)

    def _get_timestamp(self) -> str:
        """زمان فعلی را به فرمت تهران و شمسی برمی‌گرداند."""
        try:
            utc_dt = datetime.utcnow()
            tehran_tz = pytz.timezone("Asia/Tehran")
            tehran_dt = utc_dt.astimezone(tehran_tz)
            jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
            return f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
        except Exception:
            return ""

    def to_telegram_message(self) -> str:
        """سیگنال را به یک پیام تلگرام کامل و حرفه‌ای تبدیل می‌کند."""
        emoji, direction_text = self._get_signal_emoji_and_text()
        strategy_name = self.signal.get('strategy_name', 'N/A')
        entry_price = self.signal.get('entry_price', 0.0)
        stop_loss = self.signal.get('stop_loss', 0.0)
        rr_ratio = self.signal.get('risk_reward_ratio', 0.0)
        
        ai_score = self.ai_confirmation.get('confidence', 0)
        ai_explanation = self.ai_confirmation.get('explanation_fa', "AI analysis not performed.")

        message = (
            f"🔥 **AiSignalPro - NEW SIGNAL** 🔥\n\n"
            f"🪙 **{self.symbol}** | `{self.timeframe}`\n"
            f"📊 Signal: *{emoji} {direction_text}*\n"
            f"♟️ Strategy: `{strategy_name}`\n\n"
            f"🧠 AI Confidence: *{ai_score:.1f}%*\n"
            f"📊 R/R (to TP1): *1:{rr_ratio:.2f}*\n"
            f"----------------------------------------\n"
            f"📈 **Entry Price:**\n"
            f"    `{entry_price:,.4f}`\n\n"
            f"🎯 **Targets:**\n{self._format_targets()}\n\n"
            f"🛑 **Stop Loss:**\n"
            f"    `{stop_loss:,.4f}`\n"
            f"----------------------------------------\n"
            f"💡 **System Reasons:**\n{self._format_confirmations()}\n\n"
            f"🤖 **AI Analysis:**\n_{ai_explanation}_\n\n"
            f"⚠️ *Risk Management: Use 2-3% of your capital.*\n"
            f"{self._get_timestamp()}"
        )
        return message
