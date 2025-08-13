import logging
from typing import Dict, Any, Optional, Tuple, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class WhaleReversal(BaseStrategy):
    """
    WhaleReversal - (v3.0 - Reversal Strength Score Edition)
    --------------------------------------------------------------
    This world-class version evolves into a specialist hunter. It uses a sophisticated
    "Reversal Strength Score" (RSS) engine to quantify the quality of a reversal by
    scoring whale pressure intensity, rejection candle strength, and volatility context.
    It also features an adaptive, ATR-based zone detection for pinpoint accuracy.
    """
    strategy_name: str = "WhaleReversal"

    # ✅ MIRACLE UPGRADE: Default configuration for the new RSS engine
    default_config = {
        "min_reversal_score": 7,
        "weights": {
            "whale_intensity": 4,
            "rejection_wick": 3,
            "volatility_context": 2,
            "candlestick_pattern": 2
        },
        "adaptive_proximity_multiplier": 0.5, # Proximity zone is 0.5 * ATR
        "min_rr_ratio": 2.0,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }

    def _calculate_reversal_strength_score(self, direction: str, whales_data: Dict, bollinger_data: Dict) -> tuple[int, List[str]]:
        """ ✅ New Helper: The Reversal Strength Score (RSS) Engine. """
        weights = self.config.get('weights', {})
        score = 0
        confirmations = []

        # 1. Whale Pressure Intensity
        if whales_data['analysis'].get('is_whale_activity'):
            spike_score = whales_data['analysis'].get('spike_score', 0)
            if spike_score > 2.5: # Simple scoring based on intensity
                score += weights.get('whale_intensity', 4)
                confirmations.append(f"High Whale Intensity (Score: {spike_score:.2f})")

        # 2. Rejection Wick Strength
        candle = self.price_data
        wick = (candle['high'] - candle['low'])
        body = abs(candle['close'] - candle['open'])
        if wick > 0 and body / wick < 0.33: # If body is less than 1/3 of the total candle range
             if (direction == "BUY" and (candle['close'] - candle['low']) > (wick * 0.66)) or \
                (direction == "SELL" and (candle['high'] - candle['close']) > (wick * 0.66)):
                score += weights.get('rejection_wick', 3)
                confirmations.append("Strong Rejection Wick")
        
        # 3. Volatility Context
        if not bollinger_data['analysis'].get('is_in_squeeze', True):
            score += weights.get('volatility_context', 2)
            confirmations.append("High Volatility Context")

        # 4. Candlestick Pattern
        if self._get_candlestick_confirmation(direction, min_reliability='Strong'):
            score += weights.get('candlestick_pattern', 2)
            confirmations.append("Strong Candlestick Pattern")
        
        return score, confirmations

    def _find_tested_level(self, cfg: Dict, structure_data: Dict, atr_data: Dict) -> Optional[Tuple[str, float]]:
        """ ✅ New: Uses an adaptive, ATR-based proximity zone. """
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        atr_value = atr_data['values'].get('atr')
        if not all([price_low, price_high, atr_value]): return None, None
        
        proximity_zone = atr_value * cfg.get('adaptive_proximity_multiplier', 0.5)

        # Using the powerful new structure indicator data
        prox_analysis = structure_data['analysis'].get('proximity', {})
        nearest_support = prox_analysis.get('nearest_support_details', {}).get('price')
        if nearest_support and (price_low - nearest_support) < proximity_zone:
            return "BUY", nearest_support

        nearest_resistance = prox_analysis.get('nearest_resistance_details', {}).get('price')
        if nearest_resistance and (nearest_resistance - price_high) < proximity_zone:
            return "SELL", nearest_resistance
            
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        
        indicators = {name: self.get_indicator(name) for name in ['structure', 'whales', 'patterns', 'atr', 'bollinger']}
        if not all(indicators.values()): return None

        # --- 1. Location: Find a Tested Key Level ---
        signal_direction, tested_level = self._find_tested_level(cfg, indicators['structure'], indicators['atr'])
        if not signal_direction: return None
        
        # --- 2. Run the Reversal Strength Score Engine ---
        reversal_score, score_details = self._calculate_reversal_strength_score(signal_direction, indicators['whales'], indicators['bollinger'])
        
        if reversal_score < cfg.get('min_reversal_score', 7): return None

        logger.info(f"[{self.strategy_name}] High-Quality Reversal Detected: {signal_direction} with RSS {reversal_score}.")
        confirmations = {"reversal_strength_score": reversal_score, "score_details": ", ".join(score_details)}

        # --- 3. Optional Filter: Higher-Timeframe Confirmation ---
        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            if self._get_trend_confirmation(opposite_direction): return None
            confirmations['htf_filter'] = "Passed (No strong opposing HTF trend)"

        # --- 4. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        atr_value = indicators['atr'].get('values', {}).get('atr', entry_price * 0.01)
        stop_loss = tested_level - (atr_value * self.config.get('atr_sl_multiplier', 1.5)) if signal_direction == "BUY" else tested_level + (atr_value * self.config.get('atr_sl_multiplier', 1.5))
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg.get('min_rr_ratio', 1.5): return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] WHALE REVERSAL SIGNAL CONFIRMED! ✨✨")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

