import logging
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
import pytz
from jdatetime import datetime as jdatetime

logger = logging.getLogger(__name__)

class SignalAdapter:
    """
    SignalAdapter - Definitive, World-Class Version (v4.1 - Final Sync)
    --------------------------------------------------------------------
    This final version is fully synchronized with the MasterOrchestrator's
    output and the project's definitive strategy names. It adds more transparency
    to the signal messages by including confirmation details.
    """
    def __init__(self, signal_package: Dict[str, Any]):
        self.package = signal_package
        self.signal = signal_package.get("base_signal", {})
        self.ai_confirmation = signal_package.get("ai_confirmation", {})
        self.symbol = signal_package.get("symbol", "N/A")
        self.timeframe = signal_package.get("timeframe", "N/A")
        self.full_analysis = signal_package.get("full_analysis", {})

    def _get_system_confidence(self) -> float:
        """
        Assigns a confidence score based on the final, world-class strategy names.
        """
        # ✨ FIX: Updated with the final, definitive list of 12 strategy names
        priority_map = {
            "SuperSignal Confluence": 99.0,
            "ConfluenceSniper": 96.0,
            "PivotConfluenceSniper": 95.0,
            "DivergenceSniperPro": 94.0,
            "WhaleReversal": 92.0,
            "VolumeCatalystPro": 90.0,
            "IchimokuHybridPro": 88.0,
            "BreakoutHunter": 87.0,
            "ChandelierTrendRider": 86.0,
            "TrendRiderPro": 85.0,
            "KeltnerMomentumBreakout": 84.0,
            "VwapMeanReversion": 80.0,
            "EmaCrossoverStrategy": 78.0
        }
        strategy_name = self.signal.get('strategy_name', '')
        return priority_map.get(strategy_name, 75.0)

    def _get_valid_until(self) -> str:
        """
        Calculates an expiry date for the signal based on its timeframe.
        """
        ttl_map = {'5min': 1, '15min': 4, '1h': 8, '4h': 24, '1d': 72}
        hours_to_add = ttl_map.get(self.timeframe, 8)
        valid_until_utc = datetime.utcnow() + timedelta(hours=hours_to_add)
        tehran_tz = pytz.timezone("Asia/Tehran")
        tehran_dt = valid_until_utc.astimezone(tehran_tz)
        jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
        return f"⏳ Valid Until: {jalali_dt.strftime('%Y/%m/%d, %H:%M')}"

    def _get_signal_summary(self) -> str:
        """ Provides a textual summary of the signal type (Reversal or Continuation). """
        direction = self.signal.get('direction', 'HOLD')
        strategy = self.signal.get('strategy_name', '')
        if any(keyword in strategy for keyword in ["Confluence", "Sniper", "Reversal", "Reversion"]):
            return f"High-Probability {direction} Reversal"
        elif any(keyword in strategy for keyword in ["Trend", "Breakout", "Catalyst", "Ichimoku", "Cross"]):
            return f"Strong {direction} Continuation"
        return f"System Signal: {direction}"

    def _get_signal_emoji_and_text(self) -> Tuple[str, str]:
        direction = self.signal.get('direction', 'HOLD')
        if direction == 'BUY': return "🟢", "LONG"
        elif direction == 'SELL': return "🔴", "SHORT"
        return "⚪️", "NEUTRAL"

    def _format_targets(self) -> str:
        targets = self.signal.get('targets', [])
        if not targets: return "  (Calculated based on R/R)"
        return "\n".join([f"    🎯 TP{i+1}: `{t:,.4f}`" for i, t in enumerate(targets)])

    def _format_confirmations(self) -> str:
        """ Formats the confirmation details for transparency. """
        confirmations = self.signal.get('confirmations', {})
        if not confirmations: return "No details available."
        
        lines = [f"    - {key.replace('_', ' ').title()}: `{value}`" for key, value in confirmations.items()]
        return "\n".join(lines)

    def _get_timestamp(self) -> str:
        try:
            utc_dt = datetime.utcnow(); tehran_tz = pytz.timezone("Asia/Tehran")
            tehran_dt = utc_dt.astimezone(tehran_tz); jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
            return f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
        except Exception: return ""

    def to_telegram_message(self) -> str:
        """ Assembles the final, legendary Telegram message. """
        emoji, direction_text = self._get_signal_emoji_and_text()
        strategy_name = self.signal.get('strategy_name', 'N/A')
        entry_price = self.signal.get('entry_price', 0.0)
        stop_loss = self.signal.get('stop_loss', 0.0)
        rr_ratio = self.signal.get('risk_reward_ratio', 0.0)
        
        system_confidence = self._get_system_confidence()
        valid_until_str = self._get_valid_until()
        signal_summary = self._get_signal_summary()
        
        ai_confidence = self.ai_confirmation.get('confidence_percent', 0)
        ai_explanation = self.ai_confirmation.get('explanation_fa', "AI analysis was not performed.")

        # ✨ FIX: Correctly access the structure data from the flat full_analysis dictionary
        structure_analysis = self.full_analysis.get('structure', {})
        key_levels = structure_analysis.get('key_levels', {}) if structure_analysis else {}
        supports = key_levels.get('supports', []); resistances = key_levels.get('resistances', [])
        supports_str = "\n".join([f"    - `{s:,.4f}`" for s in supports[:3]]) if supports else "Not Available"
        resistances_str = "\n".join([f"    - `{r:,.4f}`" for r in resistances[:3]]) if resistances else "Not Available"

        return (
            f"🔥 **AiSignalPro - v{self.package.get('ai_version', '21.1')}** 🔥\n\n"
            f"🪙 **{self.symbol}** | `{self.timeframe}`\n"
            f"📊 Signal: *{emoji} {direction_text}*\n"
            f"♟️ Strategy: _{strategy_name}_\n\n"
            f"🎯 **System Confidence: {system_confidence:.1f}%**\n"
            f"🧠 **AI Confidence: {ai_confidence:.1f}%**\n"
            f"📊 R/R (to TP1): `1:{rr_ratio:.2f}`\n"
            f"----------------------------------------\n"
            f"📈 **Entry Price:** `{entry_price:,.4f}`\n"
            f"🛑 **Stop Loss:** `{stop_loss:,.4f}`\n\n"
            f"🎯 **Targets:**\n{self._format_targets()}\n"
            f"----------------------------------------\n"
            f"✅ **Confirmations:**\n{self._format_confirmations()}\n\n"
            f"📈 **Key Supports:**\n{supports_str}\n\n"
            f"🛡️ **Key Resistances:**\n{resistances_str}\n"
            f"----------------------------------------\n"
            f"💡 **Signal Conclusion:**\n_{signal_summary}_\n\n"
            f"🤖 **AI Analysis:**\n_{ai_explanation}_\n\n"
            f"⚠️ *Risk Management: Use 1-2% of your capital.*\n"
            f"{self._get_timestamp()}\n"
            f"{valid_until_str}"
        )
