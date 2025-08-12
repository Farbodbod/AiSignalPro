import logging
from typing import Dict, Any, Optional, List, Tuple # ✅ FIX: Import List and Tuple

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v3.1 - Compatibility Fix)
    -------------------------------------------------------------------------
    This version corrects a type hint syntax to ensure compatibility with Python
    versions older than 3.9, resolving the startup NameError.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    default_config = {
        "min_momentum_score": 4,
        "weights": {
            "adx_strength": 2,
            "cci_thrust": 3,
            "htf_alignment": 2,
            "candlestick": 1
        },
        "adx_threshold": 25.0,
        "cci_threshold": 100.0,
        "candlestick_confirmation_enabled": True,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }
    
    # ✅ FIX: Changed return type hint to use Tuple and List for compatibility
    def _calculate_momentum_score(self, direction: str, adx_data: Dict, cci_data: Dict) -> Tuple[int, List[str]]:
        """ The Momentum Power Score Engine. """
        cfg = self.config
        weights = cfg.get('weights', {})
        score = 0
        confirmations = []

        # 1. ADX Strength Confirmation
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength >= cfg.get('adx_threshold', 25.0):
            score += weights.get('adx_strength', 2)
            confirmations.append(f"ADX Strength ({adx_strength:.2f})")

        # 2. CCI Momentum Thrust Confirmation
        cci_value = cci_data.get('values', {}).get('value', 0)
        cci_threshold = cfg.get('cci_threshold', 100.0)
        if (direction == "BUY" and cci_value > cci_threshold) or \
           (direction == "SELL" and cci_value < -cci_threshold):
            score += weights.get('cci_thrust', 3)
            confirmations.append(f"CCI Thrust ({cci_value:.2f})")

        # 3. HTF Alignment Confirmation
        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(direction):
                score += weights.get('htf_alignment', 2)
                confirmations.append("HTF Aligned")

        # 4. Candlestick Confirmation
        if cfg.get('candlestick_confirmation_enabled'):
            if self._get_candlestick_confirmation(direction, min_reliability='Medium'):
                score += weights.get('candlestick', 1)
                confirmations.append("Candlestick Confirmed")
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # The core logic of this method is correct and remains unchanged.
        cfg = self.config
        if not self.price_data: return None
        
        indicators = {name: self.get_indicator(name) for name in ['keltner_channel', 'adx', 'cci', 'atr']}
        if not all(indicators.values()): return None

        keltner_data = indicators['keltner_channel']
        keltner_pos = keltner_data.get('analysis', {}).get('position')
        signal_direction = None
        if "Breakout Above" in keltner_pos: signal_direction = "BUY"
        elif "Breakdown Below" in keltner_pos: signal_direction = "SELL"
        else: return None
        
        momentum_score, score_details = self._calculate_momentum_score(signal_direction, indicators['adx'], indicators['cci'])
        
        if momentum_score < cfg.get('min_momentum_score', 4):
            return None
            
        logger.info(f"[{self.strategy_name}] High-Quality Momentum Breakout: {signal_direction} with Power Score {momentum_score}.")
        confirmations = {"power_score": momentum_score, "score_details": ", ".join(score_details)}

        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss = keltner_data.get('values', {}).get('middle_band')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # This check is now redundant as it's handled by the base class, but kept for clarity
        if not risk_params or not risk_params.get("targets"):
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] KELTNER MOMENTUM SIGNAL CONFIRMED! ✨✨")

        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
