import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperPro(BaseStrategy):
    """
    DivergenceSniperPro - (v2.1 - Corrected HTF Logic)
    -----------------------------------------------------------------------
    This version corrects the Higher-Timeframe (HTF) filter logic for reversal
    strategies, ensuring signals are correctly invalidated against strong opposing trends.
    """
    strategy_name: str = "DivergenceSniperPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "htf_confirmation_enabled": self.config.get("htf_confirmation_enabled", True),
            "htf_timeframe": self.config.get("htf_timeframe", "4h"),
            "volume_confirmation_enabled": self.config.get("volume_confirmation_enabled", True),
            "candlestick_confirmation_enabled": self.config.get("candlestick_confirmation_enabled", True),
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.0)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        if not self.price_data: return None
            
        divergence_data = self.get_indicator('divergence')
        structure_data = self.get_indicator('structure')
        wr_data = self.get_indicator('williams_r')
        atr_data = self.get_indicator('atr')
        
        if not all([divergence_data, structure_data, wr_data, atr_data]):
            return None

        if not divergence_data.get('analysis', {}).get('signals'):
            return None

        potential_signals = [s for s in divergence_data['analysis']['signals'] if "Regular" in s.get('type', '')]
        if not potential_signals:
            return None

        divergence = potential_signals[0]
        signal_direction = "BUY" if "Bullish" in divergence['type'] else "SELL"
        
        price_position = structure_data.get('analysis', {}).get('position')
        is_at_support = "Support" in price_position if price_position else False
        is_at_resistance = "Resistance" in price_position if price_position else False
        if (signal_direction == "BUY" and not is_at_support) or \
           (signal_direction == "SELL" and not is_at_resistance):
            return None
        confirmations = {"divergence_type": divergence['type'], "structure_confirmation": f"Confirmed at {price_position}"}

        # ✅ FIX: Corrected Higher-Timeframe Confirmation Logic for Reversals
        if cfg['htf_confirmation_enabled']:
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            if self._get_trend_confirmation(opposite_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Reversal attempt against a strong opposing HTF trend.")
                return None
            confirmations['htf_filter'] = f"Passed (No strong opposing trend on {cfg['htf_timeframe']})"

        if cfg['volume_confirmation_enabled']:
            if not self._get_volume_confirmation(): return None
            confirmations['volume_filter'] = "Passed (Whale activity detected)"

        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
            if not confirming_pattern: return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        wr_signal = wr_data.get('analysis', {}).get('crossover_signal', 'Hold')
        trigger_fired = (signal_direction == "BUY" and "Buy" in wr_signal) or \
                        (signal_direction == "SELL" and "Sell" in wr_signal)
        if not trigger_fired:
            return None

        logger.info(f"✨✨ [{self.strategy_name}] DIVERGENCE SNIPER SIGNAL CONFIRMED! ✨✨")

        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        pivot_price = divergence.get('pivots', [{}, {}])[1].get('price')
        if not pivot_price: return None

        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        
        if signal_direction == "BUY": stop_loss = pivot_price - (atr_value * cfg['atr_sl_multiplier'])
        else: stop_loss = pivot_price + (atr_value * cfg['atr_sl_multiplier'])

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"): return None
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
