# backend/engines/strategies/volume_reversal.py (v4.1 - Final Verified Edition)

import logging
from typing import Dict, Any, Optional, Tuple, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

# Note: The filename is volume_reversal.py, but the class name is WhaleReversal.
class WhaleReversal(BaseStrategy):
    """
    WhaleReversal - (v4.1 - Final Verified Edition)
    --------------------------------------------------------------
    This version includes a robust data availability check to prevent crashes
    and integrates the professional logging system for full transparency into
    its advanced Reversal Strength Score (RSS) engine. This is the final,
    stable version.
    """
    strategy_name: str = "WhaleReversal"

    default_config = {
        "min_reversal_score": 7,
        "weights": {
            "whale_intensity": 4,
            "rejection_wick": 3,
            "volatility_context": 2,
            "candlestick_pattern": 2
        },
        "adaptive_proximity_multiplier": 0.5,
        "min_rr_ratio": 2.0,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }

    def _calculate_reversal_strength_score(self, direction: str, whales_data: Dict, bollinger_data: Dict) -> tuple[int, List[str]]:
        # This internal calculation logic remains unchanged.
        weights = self.config.get('weights', {})
        score = 0
        confirmations = []

        if whales_data['analysis'].get('is_whale_activity'):
            spike_score = whales_data['analysis'].get('spike_score', 0)
            if spike_score > 2.5:
                score += weights.get('whale_intensity', 4)
                confirmations.append(f"High Whale Intensity (Score: {spike_score:.2f})")

        candle = self.price_data
        wick = (candle['high'] - candle['low'])
        body = abs(candle['close'] - candle['open'])
        if wick > 0 and body / wick < 0.33:
             if (direction == "BUY" and (candle['close'] - candle['low']) > (wick * 0.66)) or \
                (direction == "SELL" and (candle['high'] - candle['close']) > (wick * 0.66)):
                score += weights.get('rejection_wick', 3)
                confirmations.append("Strong Rejection Wick")
        
        if not bollinger_data['analysis'].get('is_in_squeeze', True):
            score += weights.get('volatility_context', 2)
            confirmations.append("High Volatility Context")

        if self._get_candlestick_confirmation(direction, min_reliability='Strong'):
            score += weights.get('candlestick_pattern', 2)
            confirmations.append("Strong Candlestick Pattern")
        
        return score, confirmations

    def _find_tested_level(self, cfg: Dict, structure_data: Dict, atr_data: Dict) -> Optional[Tuple[str, float]]:
        # This internal logic remains unchanged.
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        atr_value = atr_data['values'].get('atr')
        if not all([price_low, price_high, atr_value]): return None, None
        
        proximity_zone = atr_value * cfg.get('adaptive_proximity_multiplier', 0.5)

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
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        # --- 1. Data Availability Check (This block prevents the crash) ---
        required_names = ['structure', 'whales', 'patterns', 'atr', 'bollinger']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 2. Primary Trigger (Find a Tested Key Level) ---
        signal_direction, tested_level = self._find_tested_level(cfg, indicators['structure'], indicators['atr'])
        
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (Level Test)", trigger_is_ok, "No key S/R level was tested by the current price action.")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No valid entry trigger.")
            return None
        
        # --- 3. Reversal Strength Score Check ---
        reversal_score, score_details = self._calculate_reversal_strength_score(signal_direction, indicators['whales'], indicators['bollinger'])
        min_score = cfg.get('min_reversal_score', 7)
        score_is_ok = reversal_score >= min_score

        self._log_criteria("Reversal Score Check", score_is_ok, f"Score of {reversal_score} is below minimum of {min_score}.")
        if not score_is_ok:
            self._log_final_decision("HOLD", "Reversal Strength Score is too low.")
            return None
        confirmations = {"reversal_strength_score": reversal_score, "score_details": ", ".join(score_details)}

        # --- 4. HTF Confirmation Filter ---
        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
        self._log_criteria("HTF Filter", htf_ok, "A strong opposing trend was found on the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        confirmations['htf_filter'] = "Passed (No strong opposing HTF trend)"

        # --- 5. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        atr_value = indicators['atr'].get('values', {}).get('atr', entry_price * 0.01)
        stop_loss = tested_level - (atr_value * cfg.get('atr_sl_multiplier', 1.5)) if signal_direction == "BUY" else tested_level + (atr_value * cfg.get('atr_sl_multiplier', 1.5))
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        min_rr = cfg.get('min_rr_ratio', 1.5)
        rr_is_ok = risk_params and risk_params.get("risk_reward_ratio", 0) >= min_rr
        self._log_criteria("Final R/R Check", rr_is_ok, f"Failed R/R check. (Calculated: {risk_params.get('risk_reward_ratio', 0)}, Required: {min_rr})")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Final R/R check failed.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        # --- 6. Final Decision ---
        self._log_final_decision(signal_direction, "All criteria met. Whale Reversal signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

