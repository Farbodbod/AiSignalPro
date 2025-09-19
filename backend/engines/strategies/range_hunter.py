# backend/engines/strategies/range_hunter.py (v4.1 - The Gold Standard Polish)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class RangeHunterPro(BaseStrategy):
    """
    RangeHunterPro - (v4.1 - The Gold Standard Polish)
    -------------------------------------------------------------------------
    This version applies the final gold-standard polish. It fixes a critical
    "silent exit" bug and upgrades the internal scoring engine to provide
    granular, criterion-by-criterion logging for maximum transparency. The
    strategy is now considered complete, robust, and fully production-ready.
    """
    strategy_name: str = "RangeHunterPro"

    default_config: ClassVar[Dict[str, Any]] = {
        "regime_filter": {
            "enabled": True,
            "mode": "ADX_ONLY", # "ADX_ONLY" or "ADX_AND_SQUEEZE"
            "max_adx_percentile_for_range": 40.0,
        },
        "confirmation_scoring": {
            "min_score": 8,
            "weights": {
                "rsi_reversal": 4,
                "stochastic_reversal": 2,
                "divergence_confirmation": 4,
                "macd_deceleration": 5,
                "candlestick_strong": 3,
                "candlestick_medium": 2
            },
            "rsi_oversold_entry": 35.0,
            "rsi_overbought_entry": 65.0
        },
        "override_min_rr_ratio": 1.5,
        "indicator_configs": {
            "ranging_divergence": { "name": "divergence", "dependencies": { "zigzag": { "deviation": 1.0 } } }
        }
    }

    def _calculate_confirmation_score(self, direction: str, cfg: Dict, indicators: Dict) -> Tuple[int, List[Dict]]:
        weights, score = cfg.get('weights', {}), 0
        confirmation_details = []

        def check_and_log(name: str, weight_key: str, condition: bool, reason: str):
            nonlocal score
            self._log_criteria(f"Score: {name}", condition, reason)
            if condition:
                points = weights.get(weight_key, 0)
                score += points
                confirmation_details.append({'criterion': name, 'value': reason})

        rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
        rsi_cond = (direction == "BUY" and rsi_val <= cfg.get('rsi_oversold_entry', 35.0)) or \
                   (direction == "SELL" and rsi_val >= cfg.get('rsi_overbought_entry', 65.0))
        check_and_log("RSI Reversal", "rsi_reversal", rsi_cond, f"Value: {rsi_val:.2f}")

        stoch_pos = self._safe_get(indicators, ['stochastic', 'analysis', 'position'], "")
        stoch_cond = (direction == "BUY" and "Oversold" in stoch_pos) or \
                     (direction == "SELL" and "Overbought" in stoch_pos)
        check_and_log("Stochastic Reversal", "stochastic_reversal", stoch_cond, f"Position: {stoch_pos}")

        macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {})
        hist_state = self._safe_get(macd_analysis, ['context', 'histogram_state'])
        macd_cond = (direction == "BUY" and hist_state == "White_Up") or \
                    (direction == "SELL" and hist_state == "White_Down")
        check_and_log("MACD Deceleration", "macd_deceleration", macd_cond, f"State: {hist_state}")

        div_analysis = self._safe_get(indicators, ['ranging_divergence', 'analysis'], {})
        div_cond = (direction == "BUY" and div_analysis.get('has_regular_bullish_divergence')) or \
                   (direction == "SELL" and div_analysis.get('has_regular_bearish_divergence'))
        check_and_log("Divergence Confirmed", "divergence_confirmation", div_cond, f"Bull: {div_analysis.get('has_regular_bullish_divergence')}")

        confirming_pattern = self._get_candlestick_confirmation(direction, min_reliability='Medium')
        if confirming_pattern:
            reliability = (confirming_pattern.get('reliability') or '').capitalize()
            pattern_name = confirming_pattern.get('name')
            if reliability == 'Strong':
                check_and_log(f"Strong Candlestick", "candlestick_strong", True, f"Pattern: {pattern_name}")
            elif reliability == 'Medium':
                check_and_log(f"Medium Candlestick", "candlestick_medium", True, f"Pattern: {pattern_name}")
        
        return score, confirmation_details

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "Price data is not available for this candle.")
            return None

        required_names = ['bollinger', 'adx', 'rsi', 'atr', 'stochastic', 'patterns', 'structure', 'pivots', 'macd', 'ranging_divergence']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None or not data.get('values') for data in indicators.values()):
            self._log_final_decision("HOLD", "One or more required indicators are missing/invalid.")
            return None

        regime_cfg = cfg.get('regime_filter', {})
        if regime_cfg.get('enabled'):
            adx_percentile = self._safe_get(indicators, ['adx', 'analysis', 'adx_percentile'], 100.0)
            if adx_percentile > regime_cfg.get('max_adx_percentile_for_range', 40.0):
                self._log_final_decision("HOLD", f"Market is not ranging (ADX Percentile={adx_percentile:.2f}).")
                return None
            self._log_criteria("ADX Ranging Filter", True, f"ADX % is {adx_percentile:.2f}")

            if regime_cfg.get('mode') == "ADX_AND_SQUEEZE":
                is_in_squeeze = self._safe_get(indicators, ['bollinger', 'analysis', 'is_in_squeeze'], False)
                if not is_in_squeeze:
                    self._log_final_decision("HOLD", "Market volatility is too high (Bollinger Bands are not in a squeeze).")
                    return None
                self._log_criteria("Bollinger Squeeze Filter", True, "Market is in a low-volatility squeeze.")
        
        bollinger_values = indicators['bollinger']['values']
        upper_band, lower_band = bollinger_values.get('upper_band'), bollinger_values.get('lower_band')
        if not self._is_valid_number(upper_band, lower_band):
            self._log_final_decision("HOLD", "Bollinger Bands not available."); return None
        signal_direction = None
        if self.price_data.get('low') <= lower_band: signal_direction = "BUY"
        elif self.price_data.get('high') >= upper_band: signal_direction = "SELL"
        if not signal_direction: self._log_final_decision("HOLD", "Price is not at an extreme of the range."); return None
        self._log_criteria("Price at Band", True, f"Price touched {'LOWER' if signal_direction == 'BUY' else 'UPPER'} band.")

        scoring_cfg = cfg.get('confirmation_scoring', {})
        score, details_list = self._calculate_confirmation_score(signal_direction, scoring_cfg, indicators)
        min_score = scoring_cfg.get('min_score', 8)
        if score < min_score:
            self._log_final_decision("HOLD", f"Confirmation score {score} is below minimum of {min_score}.")
            return None
        self._log_criteria("Confirmation Score", True, f"Score={score} vs min={min_score}. Details: {details_list}")

        entry_price = self.price_data.get('close')
        if not self._is_valid_number(entry_price) or entry_price <= 0:
            self._log_final_decision("HOLD", f"Invalid entry price: {entry_price}."); return None
        self.config['override_min_rr_ratio'] = cfg.get('override_min_rr_ratio', 1.5)
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)
        if not risk_params:
            self._log_final_decision("HOLD", "OHRE v3.0 failed to generate a valid risk plan."); return None
        
        confirmations = {
            "market_regime": f"RANGING (Mode: {regime_cfg.get('mode')})",
            "final_score": score,
            "details": details_list, # ✅ POLISH: Use the list of dicts directly
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "rr_check": f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        }
        self._log_final_decision(signal_direction, "All criteria met. Range Hunter Pro signal confirmed.")
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

