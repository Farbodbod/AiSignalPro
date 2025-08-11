import logging
from typing import Dict, Any, Optional, Tuple
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class WhaleReversal(BaseStrategy):
    """
    WhaleReversal - (v2.1 - Corrected HTF Logic)
    --------------------------------------------------------------
    This version corrects the Higher-Timeframe (HTF) filter logic for reversal
    strategies, ensuring signals are correctly invalidated against strong opposing trends.
    """
    strategy_name: str = "WhaleReversal"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "proximity_percent": float(self.config.get("proximity_percent", 0.5)),
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.5)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def _find_tested_level(self, cfg: Dict[str, Any], structure_data: Dict[str, Any]) -> Optional[Tuple[str, float]]:
        """
        Finds the closest key Support or Resistance level that the current
        price is actively testing.
        """
        price_low = self.price_data.get('low'); price_high = self.price_data.get('high')
        if not all([price_low, price_high]): return None, None
        nearest_support = structure_data['analysis']['proximity'].get('nearest_support')
        if nearest_support and abs(price_low - nearest_support) / nearest_support * 100 < cfg['proximity_percent']:
            return "BUY", nearest_support
        nearest_resistance = structure_data['analysis']['proximity'].get('nearest_resistance')
        if nearest_resistance and abs(price_high - nearest_resistance) / nearest_resistance * 100 < cfg['proximity_percent']:
            return "SELL", nearest_resistance
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: return None
        structure_data = self.get_indicator('structure')
        whales_data = self.get_indicator('whales')
        patterns_data = self.get_indicator('patterns')
        atr_data = self.get_indicator('atr')
        if not all([structure_data, whales_data, patterns_data, atr_data]): return None

        signal_direction, tested_level = self._find_tested_level(cfg, structure_data)
        if not signal_direction: return None
        
        confirmations = {"location_confirmation": f"Tested key S/R at {tested_level:.5f}"}

        if not whales_data.get('analysis', {}).get('is_whale_activity'): return None
        
        whale_pressure = whales_data['analysis'].get('pressure')
        is_absorption = (signal_direction == "BUY" and "Buying" in whale_pressure)
        is_distribution = (signal_direction == "SELL" and "Selling" in whale_pressure)

        if not (is_absorption or is_distribution): return None
        confirmations['force_confirmation'] = f"Passed (Whale {whale_pressure} detected)"
        
        confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
        if not confirming_pattern: return None
        confirmations['timing_confirmation'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # ✅ FIX: Corrected Higher-Timeframe Confirmation Logic for Reversals
        if cfg['htf_confirmation_enabled']:
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            if self._get_trend_confirmation(opposite_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Reversal attempt against a strong opposing HTF trend.")
                return None
            confirmations['htf_filter'] = f"Passed (No strong opposing trend on {cfg['htf_timeframe']})"

        entry_price = self.price_data.get('close')
        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        
        if signal_direction == "BUY": stop_loss = tested_level - (atr_value * cfg['atr_sl_multiplier'])
        else: stop_loss = tested_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']: return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] WHALE REVERSAL SIGNAL CONFIRMED! ✨✨")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

