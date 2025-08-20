# Backend/engines/signal_adapter.py (v5.0 - The Miracle Edition)

import logging
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timedelta
import pytz
from jdatetime import datetime as jdatetime

logger = logging.getLogger(__name__)

class SignalAdapter:
    """
    SignalAdapter (v5.0 - The Miracle Edition)
    ---------------------------------------------------------------------------
    This definitive version introduces a major architectural upgrade, making the
    adapter self-aware of the indicator map ('_indicator_map'). This allows it
    to intelligently find and parse data from indicators with dynamic keys,
    like 'structure'. It also incorporates an anti-fragile fix for AI confidence
    parsing and refactors data extraction for ultimate clarity and robustness.
    """
    def __init__(self, signal_package: Dict[str, Any]):
        # --- Core Packages ---
        self.package = signal_package
        self.base_signal = signal_package.get("base_signal", {})
        self.ai_confirmation = signal_package.get("ai_confirmation", {})
        self.full_analysis = signal_package.get("full_analysis", {})
        self.indicator_map = self.full_analysis.get("_indicator_map", {})

        # --- Primary Signal Details ---
        self.symbol = signal_package.get("symbol", "N/A")
        self.timeframe = signal_package.get("timeframe", "N/A")
        self.strategy_name = self.base_signal.get('strategy_name', 'N/A')
        self.direction = self.base_signal.get('direction', 'HOLD')
        self.entry_price = self.base_signal.get('entry_price', 0.0)
        self.stop_loss = self.base_signal.get('stop_loss', 0.0)
        self.targets = self.base_signal.get('targets', [])
        self.rr_ratio = self.base_signal.get('risk_reward_ratio', 0.0)
        self.confirmations = self.base_signal.get('confirmations', {})
        self.engine_version = self.package.get('engine_version', 'N/A')

    def _get_indicator_analysis(self, indicator_name: str) -> Optional[Dict[str, Any]]:
        """Intelligently finds an indicator's analysis using the indicator_map."""
        unique_key = self.indicator_map.get(indicator_name)
        if not unique_key:
            logger.warning(f"Could not find unique key for '{indicator_name}' in indicator_map for {self.symbol}@{self.timeframe}")
            return None
        return self.full_analysis.get(unique_key)

    def _get_system_confidence(self) -> float:
        priority_map = {
            "SuperSignal Confluence": 99.0, "ConfluenceSniper": 96.0,
            "PivotConfluenceSniper": 95.0, "DivergenceSniperPro": 94.0,
            "WhaleReversal": 92.0, "VolumeCatalystPro": 90.0,
            "IchimokuHybridPro": 88.0, "BreakoutHunter": 87.0,
            "ChandelierTrendRider": 86.0, "TrendRiderPro": 85.0,
            "KeltnerMomentumBreakout": 84.0, "VwapMeanReversion": 80.0,
            "EmaCrossoverStrategy": 78.0
        }
        return priority_map.get(self.strategy_name, 75.0)

    def _get_valid_until(self) -> str:
        ttl_map = {'5m': 2, '15m': 4, '1h': 8, '4h': 24, '1d': 72}
        hours_to_add = ttl_map.get(self.timeframe, 8)
        valid_until_utc = datetime.utcnow() + timedelta(hours=hours_to_add)
        tehran_tz = pytz.timezone("Asia/Tehran")
        tehran_dt = valid_until_utc.astimezone(tehran_tz)
        jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
        return f"⏳ Valid Until: {jalali_dt.strftime('%Y/%m/%d, %H:%M')}"

    def _get_signal_summary(self) -> str:
        if any(keyword in self.strategy_name for keyword in ["Confluence", "Sniper", "Reversal", "Reversion"]):
            return f"High-Probability {self.direction} Reversal"
        elif any(keyword in self.strategy_name for keyword in ["Trend", "Breakout", "Catalyst", "Ichimoku", "Cross"]):
            return f"Strong {self.direction} Continuation"
        return f"System Signal: {self.direction}"

    def _get_signal_emoji_and_text(self) -> Tuple[str, str]:
        if self.direction == 'BUY': return "🟢", "LONG"
        elif self.direction == 'SELL': return "🔴", "SHORT"
        return "⚪️", "NEUTRAL"

    def _format_targets(self) -> str:
        if not self.targets: return "  (Calculated based on R/R)"
        return "\n".join([f"    🎯 TP{i+1}: `{t:,.4f}`" for i, t in enumerate(self.targets)])

    def _format_confirmations(self) -> str:
        if not self.confirmations: return "No details available."
        lines = [f"    - {str(key).replace('_', ' ').title()}: `{value}`" for key, value in self.confirmations.items()]
        return "\n".join(lines)

    def _get_key_levels(self) -> Tuple[str, str]:
        """Extracts and formats support and resistance levels."""
        structure_analysis = self._get_indicator_analysis('structure')
        supports_str = "Not Available"
        resistances_str = "Not Available"

        if structure_analysis and isinstance(structure_analysis.get('key_levels'), dict):
            supports = structure_analysis['key_levels'].get('supports', [])
            resistances = structure_analysis['key_levels'].get('resistances', [])
            
            # ✅ FIX: Correctly access the 'price' key in the list of dicts
            if supports:
                supports_str = "\n".join([f"    - `{s.get('price', 0):,.4f}`" for s in supports[:3]])
            if resistances:
                resistances_str = "\n".join([f"    - `{r.get('price', 0):,.4f}`" for r in resistances[:3]])
        
        return supports_str, resistances_str

    def _get_ai_details(self) -> Tuple[float, str]:
        """Extracts AI confidence and explanation with anti-fragile logic."""
        # ✅ FIX: Accept both 'confidence_percent' and 'confidence' for robustness
        confidence_val = self.ai_confirmation.get("confidence_percent")
        if confidence_val is None:
            confidence_val = self.ai_confirmation.get("confidence") # Fallback
        
        ai_confidence = float(confidence_val or 0)
        ai_explanation = self.ai_confirmation.get('explanation_fa', "AI analysis was not performed.")
        return ai_confidence, ai_explanation
        
    def _get_timestamp(self) -> str:
        try:
            utc_dt = datetime.utcnow(); tehran_tz = pytz.timezone("Asia/Tehran")
            tehran_dt = utc_dt.astimezone(tehran_tz); jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
            return f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
        except Exception: return ""

    def to_telegram_message(self) -> str:
        emoji, direction_text = self._get_signal_emoji_and_text()
        system_confidence = self._get_system_confidence()
        valid_until_str = self._get_valid_until()
        signal_summary = self._get_signal_summary()
        ai_confidence, ai_explanation = self._get_ai_details()
        supports_str, resistances_str = self._get_key_levels()
        
        return (
            f"🔥 **AiSignalPro - Signal v{self.engine_version}** 🔥\n\n"
            f"🪙 **{self.symbol}** | `{self.timeframe}`\n"
            f"📊 Signal: *{emoji} {direction_text}*\n"
            f"♟️ Strategy: _{self.strategy_name}_\n\n"
            f"🎯 **System Confidence: {system_confidence:.1f}%**\n"
            f"🧠 **AI Confidence: {ai_confidence:.1f}%**\n"
            f"📊 R/R (to TP1): `1:{self.rr_ratio:.2f}`\n"
            f"----------------------------------------\n"
            f"📈 **Entry Price:** `{self.entry_price:,.4f}`\n"
            f"🛑 **Stop Loss:** `{self.stop_loss:,.4f}`\n\n"
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

