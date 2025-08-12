import logging
from typing import Dict, Any, Optional, List, Tuple # ✅ FIX: Import List and Tuple

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BreakoutHunter(BaseStrategy):
    """
    BreakoutHunter - (v3.1 - Compatibility Fix)
    ----------------------------------------------------------------
    This version corrects a type hint syntax to ensure compatibility with Python
    versions older than 3.9, resolving the startup NameError.
    """
    strategy_name: str = "BreakoutHunter"

    default_config = {
        "min_breakout_score": 6,
        "rr_requirements": { "low_score_threshold": 7, "high_rr": 2.5, "default_rr": 1.5 },
        "weights": {
            "squeeze_release": 3,
            "volume_catalyst": 3,
            "momentum_thrust": 2,
            "htf_alignment": 2
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    # ✅ FIX: Changed return type hint to use Tuple and List for compatibility
    def _calculate_breakout_score(self, signal_direction: str, bollinger_data: Dict, whales_data: Dict, cci_data: Dict) -> Tuple[int, List[str]]:
        """
        The Breakout Power Score Engine.
        This method calculates a weighted score for the quality of the breakout.
        """
        cfg = self.config
        weights = cfg.get('weights', {})
        score = 0
        confirmations = []

        # Volatility Release Confirmation
        if bollinger_data['analysis'].get('is_squeeze_release'):
            score += weights.get('squeeze_release', 3)
            confirmations.append("Volatility Squeeze Release")
        
        # Volume Catalyst Confirmation
        if whales_data['analysis'].get('is_whale_activity'):
            whale_pressure = whales_data['analysis'].get('pressure', '')
            if (signal_direction == "BUY" and "Buying" in whale_pressure) or \
               (signal_direction == "SELL" and "Selling" in whale_pressure):
                score += weights.get('volume_catalyst', 3)
                confirmations.append("Whale Volume Catalyst")

        # Momentum Thrust Confirmation (using CCI)
        cci_threshold = cfg.get('cci_threshold', 100.0)
        cci_value = cci_data.get('values', {}).get('value', 0)
        if (signal_direction == "BUY" and cci_value > cci_threshold) or \
           (signal_direction == "SELL" and cci_value < -cci_threshold):
            score += weights.get('momentum_thrust', 2)
            confirmations.append(f"Momentum Thrust (CCI: {cci_value:.2f})")
            
        # HTF Alignment Confirmation
        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(signal_direction):
                score += weights.get('htf_alignment', 2)
                confirmations.append(f"HTF Trend Aligned")
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # The core logic of this method is correct and remains unchanged.
        cfg = self.config
        if not self.price_data: return None
        
        donchian_data = self.get_indicator('donchian_channel')
        bollinger_data = self.get_indicator('bollinger')
        whales_data = self.get_indicator('whales')
        cci_data = self.get_indicator('cci')
        atr_data = self.get_indicator('atr')
        
        if not all([donchian_data, bollinger_data, whales_data, cci_data, atr_data]):
            return None

        donchian_signal = donchian_data.get('analysis', {}).get('signal')
        signal_direction = None
        if "Buy" in donchian_signal: signal_direction = "BUY"
        elif "Sell" in donchian_signal: signal_direction = "SELL"
        else: return None
        
        breakout_score, score_details = self._calculate_breakout_score(signal_direction, bollinger_data, whales_data, cci_data)
        
        if breakout_score < cfg.get('min_breakout_score', 6):
            return None
            
        logger.info(f"[{self.strategy_name}] High-Quality Breakout Detected: {signal_direction} with Power Score {breakout_score}.")
        confirmations = {"power_score": breakout_score, "score_details": ", ".join(score_details)}
        
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss = donchian_data.get('values', {}).get('middle_band')
        if not stop_loss:
            atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.02)
            stop_loss = entry_price - (atr_value * 2) if signal_direction == "BUY" else entry_price + (atr_value * 2)
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        rr_reqs = cfg.get('rr_requirements', {})
        min_rr_ratio = rr_reqs.get('high_rr', 2.5) if breakout_score < rr_reqs.get('low_score_threshold', 7) else rr_reqs.get('default_rr', 1.5)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < min_rr_ratio:
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')}, Required: {min_rr_ratio})"
        
        logger.info(f"✨✨ [{self.strategy_name}] BREAKOUT HUNTER SIGNAL CONFIRMED! ✨✨")

        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
