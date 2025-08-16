# backend/engines/strategies/volume_reversal.py (v4.3 - SyntaxError FIX)

import logging
from typing import Dict, Any, Optional, Tuple, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class WhaleReversal(BaseStrategy):
    """
    WhaleReversal - (v4.3 - SyntaxError FIX)
    --------------------------------------------------------------
    This version fixes a critical SyntaxError in the deep validation logging
    message, allowing the application to start correctly.
    """
    strategy_name: str = "WhaleReversal"

    default_config = {
        # ... (بخش کانفیگ بدون تغییر باقی می‌ماند) ...
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

    # --- تمام توابع کمکی (_calculate_reversal_strength_score, _find_tested_level) بدون تغییر باقی می‌مانند ---
    def _calculate_reversal_strength_score(self, direction: str, whales_data: Dict, bollinger_data: Dict) -> tuple[int, List[str]]:
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
        
        required_names = ['structure', 'whales', 'patterns', 'atr', 'bollinger']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        if missing_indicators:
            reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}"
            self._log_criteria("Data Availability", False, reason)
            self._log_final_decision("HOLD", reason)
            return None

        critical_paths = {
            'structure': ['analysis', 'proximity'],
            'atr': ['values', 'atr'],
            'whales': ['analysis']
        }
        for name, path in critical_paths.items():
            obj = indicators[name]
            for key in path:
                obj = obj.get(key) if isinstance(obj, dict) else None
                if obj is None:
                    # ✅ SYNTAX FIX: Corrected the f-string formatting
                    reason = f"Indicator '{name}' is missing critical nested data: '{'.'.join(path)}'"
                    self._log_criteria("Deep Data Validation", False, reason)
                    self._log_final_decision("HOLD", reason)
                    return None
        self._log_criteria("Deep Data Validation", True, "All critical nested data paths are valid.")
        
        # --- بقیه کد check_signal بدون تغییر باقی می‌ماند ---
        signal_direction, tested_level = self._find_tested_level(cfg, indicators['structure'], indicators['atr'])
        
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (Level Test)", trigger_is_ok, "No key S/R level was tested by the current price action.")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No valid entry trigger.")
            return None
        
        reversal_score, score_details = self._calculate_reversal_strength_score(signal_direction, indicators['whales'], indicators['bollinger'])
        min_score = cfg.get('min_reversal_score', 7)
        score_is_ok = reversal_score >= min_score

        self._log_criteria("Reversal Score Check", score_is_ok, f"Score of {reversal_score} is below minimum of {min_score}.")
        if not score_is_ok:
            self._log_final_decision("HOLD", "Reversal Strength Score is too low.")
            return None
        confirmations = {"reversal_strength_score": reversal_score, "score_details": ", ".join(score_details)}

        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
        self._log_criteria("HTF Filter", htf_ok, "A strong opposing trend was found on the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        confirmations['htf_filter'] = "Passed (No strong opposing HTF trend)"

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
        
        self._log_final_decision(signal_direction, "All criteria met. Whale Reversal signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

