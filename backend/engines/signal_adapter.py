# Backend/engines/signal_adapter.py (v5.1 - The Universal Levels Protocol)

import logging
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timedelta
import pytz
from jdatetime import datetime as jdatetime

logger = logging.getLogger(__name__)

class SignalAdapter:
    """
    SignalAdapter (v5.1 - The Universal Levels Protocol)
    ---------------------------------------------------------------------------
    This definitive version implements the "Universal Levels Protocol", a major
    architectural upgrade. It intelligently prioritizes key levels provided
    directly by a strategy over the global 'structure' indicator, creating a
    truly modular and future-proof system. It also includes anti-fragile fixes
    for AI confidence parsing and features enhanced, professional-grade code
    structure, documentation, and type hinting.
    """
    def __init__(self, signal_package: Dict[str, Any]):
        """
        Initializes the adapter by extracting all necessary data from the signal package.
        This clean separation of data extraction from presentation logic improves clarity.
        """
        # --- Core Packages ---
        self.package: Dict[str, Any] = signal_package
        self.base_signal: Dict[str, Any] = signal_package.get("base_signal", {})
        self.ai_confirmation: Dict[str, Any] = signal_package.get("ai_confirmation", {})
        self.full_analysis: Dict[str, Any] = signal_package.get("full_analysis", {})
        self.indicator_map: Dict[str, str] = self.full_analysis.get("_indicator_map", {})

        # --- Primary Signal Details ---
        self.symbol: str = signal_package.get("symbol", "N/A")
        self.timeframe: str = signal_package.get("timeframe", "N/A")
        self.strategy_name: str = self.base_signal.get('strategy_name', 'N/A')
        self.direction: str = self.base_signal.get('direction', 'HOLD')
        self.entry_price: float = self.base_signal.get('entry_price', 0.0)
        self.stop_loss: float = self.base_signal.get('stop_loss', 0.0)
        self.targets: List[float] = self.base_signal.get('targets', [])
        self.rr_ratio: float = self.base_signal.get('risk_reward_ratio', 0.0)
        self.confirmations: Dict[str, Any] = self.base_signal.get('confirmations', {})
        self.engine_version: str = self.package.get('engine_version', 'N/A')

    def _get_indicator_analysis(self, indicator_name: str) -> Optional[Dict[str, Any]]:
        """
        Intelligently finds an indicator's full analysis object from the main
        analysis package by using the essential '_indicator_map'.

        Args:
            indicator_name: The simple name of the indicator (e.g., 'structure').

        Returns:
            The full analysis dictionary for that indicator, or None if not found.
        """
        unique_key = self.indicator_map.get(indicator_name)
        if not unique_key:
            logger.warning(f"Could not find unique key for '{indicator_name}' in indicator_map for {self.symbol}@{self.timeframe}")
            return None
        return self.full_analysis.get(unique_key)

    def _get_system_confidence(self) -> float:
        """Calculates a heuristic system confidence based on strategy priority."""
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
        """Generates a localized and Jalali-converted expiration timestamp."""
        ttl_map = {'5m': 2, '15m': 4, '1h': 8, '4h': 24, '1d': 72}
        hours_to_add = ttl_map.get(self.timeframe, 8)
        valid_until_utc = datetime.utcnow() + timedelta(hours=hours_to_add)
        tehran_tz = pytz.timezone("Asia/Tehran")
        tehran_dt = valid_until_utc.astimezone(tehran_tz)
        jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
        return f"⏳ Valid Until: {jalali_dt.strftime('%Y/%m/%d, %H:%M')}"

    def _get_signal_summary(self) -> str:
        """Generates a smart, context-aware conclusion for the signal."""
        if any(keyword in self.strategy_name for keyword in ["Confluence", "Sniper", "Reversal", "Reversion"]):
            return f"High-Probability {self.direction} Reversal"
        elif any(keyword in self.strategy_name for keyword in ["Trend", "Breakout", "Catalyst", "Ichimoku", "Cross"]):
            return f"Strong {self.direction} Continuation"
        return f"System Signal: {self.direction}"

    def _get_signal_emoji_and_text(self) -> Tuple[str, str]:
        """Returns the appropriate emoji and text for the signal direction."""
        if self.direction == 'BUY': return "🟢", "LONG"
        elif self.direction == 'SELL': return "🔴", "SHORT"
        return "⚪️", "NEUTRAL"

    def _format_targets(self) -> str:
        """Formats the target prices for display."""
        if not self.targets: return "  (Calculated based on R/R)"
        return "\n".join([f"    🎯 TP{i+1}: `{t:,.4f}`" for i, t in enumerate(self.targets)])

    def _format_confirmations(self) -> str:
        """Formats the strategy's confirmation details."""
        if not self.confirmations: return "No details available."
        lines = [f"    - {str(key).replace('_', ' ').title()}: `{value}`" for key, value in self.confirmations.items()]
        return "\n".join(lines)

    def _get_key_levels(self) -> Tuple[str, str]:
        """
        Extracts and formats S/R levels using the Universal Levels Protocol.
        Priority 1: Levels provided directly by the strategy in the base_signal.
        Priority 2: Fallback to the global 'structure' indicator.
        """
        supports, resistances = [], []
        
        # Priority 1: Check the strategy's own signal package first.
        if 'key_levels' in self.base_signal and isinstance(self.base_signal['key_levels'], dict):
            logger.info(f"Using strategy-provided key levels from '{self.strategy_name}'.")
            levels = self.base_signal['key_levels']
            supports = levels.get('supports', [])
            resistances = levels.get('resistances', [])
        # Priority 2: Fallback to the global structure indicator.
        else:
            logger.info(f"No strategy-provided levels found. Falling back to global 'structure' indicator.")
            structure_analysis = self._get_indicator_analysis('structure')
            if structure_analysis and isinstance(structure_analysis.get('key_levels'), dict):
                levels = structure_analysis['key_levels']
                supports = levels.get('supports', [])
                resistances = levels.get('resistances', [])

        supports_str = "Not Available"
        resistances_str = "Not Available"

        if supports:
            supports_str = "\n".join([f"    - `{s.get('price', 0):,.4f}`" for s in supports[:3]])
        if resistances:
            resistances_str = "\n".join([f"    - `{r.get('price', 0):,.4f}`" for r in resistances[:3]])
        
        return supports_str, resistances_str

    def _get_ai_details(self) -> Tuple[float, str]:
        """Extracts AI confidence and explanation with anti-fragile logic."""
        confidence_val = self.ai_confirmation.get("confidence_percent")
        if confidence_val is None:
            confidence_val = self.ai_confirmation.get("confidence") # Fallback
        
        ai_confidence = float(confidence_val or 0)
        ai_explanation = self.ai_confirmation.get('explanation_fa', "AI analysis was not performed.")
        return ai_confidence, ai_explanation
        
    def _get_timestamp(self) -> str:
        """Generates a localized and Jalali-converted creation timestamp."""
        try:
            utc_dt = datetime.utcnow()
            tehran_tz = pytz.timezone("Asia/Tehran")
            tehran_dt = utc_dt.astimezone(tehran_tz)
            jalali_dt = jdatetime.fromgregorian(datetime=tehran_dt)
            return f"⏰ {jalali_dt.strftime('%Y/%m/%d, %H:%M:%S')}"
        except Exception: 
            return ""

    def to_telegram_message(self) -> str:
        """
        Constructs the final, beautifully formatted Telegram message from all components.
        This method is now purely for presentation.
        """
        emoji, direction_text = self._get_signal_emoji_and_text()
        system_confidence = self._get_system_confidence()
        valid_until_str = self._get_valid_until()
        signal_summary = self._get_signal_summary()
        ai_confidence, ai_explanation = self._get_ai_details()
        supports_str, resistances_str = self._get_key_levels()
        
        return (
            f"🔥 **AiSignalPro - Signal v{self.engine_version}** 🔥\n\n"
            f"🌕 **{self.symbol}** | `{self.timeframe}`\n"
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
